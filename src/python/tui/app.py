"""TUI Application - Textual-based Terminal Interface for RCY.

A command-line interface for RCY breakbeat slicer with:
- ASCII waveform display
- Keyboard-driven segment playback (1-0, q-p keys)
- Command input (/open, /slice, /export, etc.)
- Agent-based interaction (!slice, !preset, etc.)
"""

import os
import threading
import time
from pathlib import Path
from typing import Optional
import logging

from textual.app import App, ComposeResult
from textual.widgets import Static, TextArea
from textual.binding import Binding
from textual import events



from audio_processor import WavAudioProcessor
from segment_manager import get_segment_manager
from config_manager import config
from tui.widgets import WaveformWidget, CommandInput
from tui.agents import create_agent, BaseAgent
from tui.agents.base import ToolRegistry

logger = logging.getLogger(__name__)

# Key mappings for segment playback
SEGMENT_KEYS = {
    '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
    '6': 6, '7': 7, '8': 8, '9': 9, '0': 10,
    'q': 11, 'w': 12, 'e': 13, 'r': 14, 't': 15,
    'y': 16, 'u': 17, 'i': 18, 'o': 19, 'p': 20,
}


class PatternPlayer:
    """Plays a pattern of segments with optional looping."""

    def __init__(self, app: 'RCYApp'):
        self.app = app
        self.pattern: list[int] = []
        self.loop = False
        self.playing = False
        self.current_index = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self, pattern: list[int], loop: bool) -> None:
        """Start playing a pattern."""
        self.stop()  # Stop any existing playback

        self.pattern = pattern
        self.loop = loop
        self.current_index = 0
        self.playing = True
        self._stop_event.clear()

        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop pattern playback."""
        self._stop_event.set()
        self.playing = False
        if self.app.model:
            self.app.model.stop_playback()

    def _play_loop(self) -> None:
        """Background thread for pattern playback."""
        # Cache boundaries and times outside the loop
        boundaries = self.app.segment_manager.get_boundaries()
        if len(boundaries) < 2:
            self.playing = False
            return

        sample_rate = self.app.model.sample_rate
        times = [b / sample_rate for b in boundaries]
        num_segments = len(times) - 1

        # Cache tempo settings
        tempo_enabled = self.app.model.playback_tempo_enabled
        tempo_ratio = 1.0
        if tempo_enabled and self.app.model.source_bpm > 0:
            tempo_ratio = self.app.model.target_bpm / self.app.model.source_bpm

        pattern_len = len(self.pattern)

        while not self._stop_event.is_set():
            if not self.pattern:
                break

            segment_index = self.pattern[self.current_index]

            if segment_index < 1 or segment_index > num_segments:
                self.current_index = (self.current_index + 1) % pattern_len
                continue

            start_time = times[segment_index - 1]
            end_time = times[segment_index]
            duration = end_time - start_time

            if tempo_enabled:
                duration = duration / tempo_ratio

            # Play the segment (no UI update during loop - too slow)
            self.app.model.play_segment(start_time, end_time)

            # Wait for segment to finish
            sleep_time = duration
            while sleep_time > 0 and not self._stop_event.is_set():
                time.sleep(min(0.05, sleep_time))
                sleep_time -= 0.05

            if self._stop_event.is_set():
                break

            self.current_index += 1
            if self.current_index >= pattern_len:
                if self.loop:
                    self.current_index = 0
                else:
                    break

        self.playing = False


class RCYApp(App):
    """Main Textual TUI application for RCY."""

    CSS_PATH = "rcy.tcss"

    BINDINGS = [
        Binding("space", "play_selection", "Play L→R", show=False),
        Binding("escape", "stop", "Stop", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self, preset_id: str = 'amen_classic'):
        super().__init__()
        self.preset_id = preset_id
        self.model: Optional[WavAudioProcessor] = None
        self.segment_manager = get_segment_manager()

        # View state
        self.start_marker = 0.0
        self.end_marker = 0.0
        self.zoom_start = 0.0
        self.zoom_end = 0.0
        self.num_measures = 1
        self.playback_mode = "loop"
        self.target_bpm: Optional[float] = None

        # Pattern player
        self.pattern_player = PatternPlayer(self)

        # Agent system
        self.agent: Optional[BaseAgent] = None

        # Status message
        self._status = "Welcome to RCY TUI. Type /help for commands."

    def compose(self) -> ComposeResult:
        """Create the application layout."""
        yield WaveformWidget(id="waveform")
        yield TextArea(id="output", read_only=True, soft_wrap=True)
        yield CommandInput(id="command")

    def on_mount(self) -> None:
        """Initialize when app is mounted."""
        self._init_agent()
        self._append_output(self._status)
        if not self.init_model():
            self._append_output("Failed to load preset. Use /preset <name>")
        self._update_waveform()
        self.query_one("#command", CommandInput).focus()

    def _init_agent(self) -> None:
        """Initialize the agent from config."""
        agent_type = config.get_setting("agent", "type", "default")

        registry = ToolRegistry()
        self._register_agent_tools(registry)

        try:
            self.agent = create_agent(agent_type, registry)
            logger.info(f"Initialized {agent_type} agent")
        except ValueError as e:
            logger.warning(f"Failed to create agent: {e}, using default")
            self.agent = create_agent("default", registry)

    def _register_agent_tools(self, registry: ToolRegistry) -> None:
        """Register tool handlers with the agent's tool registry."""
        from tui.agents.tools import (
            SliceTool, PresetTool, OpenTool, MarkersTool,
            SetTool, TempoTool, PlayTool, StopTool, ExportTool,
            ZoomTool, ModeTool, HelpTool, PresetsTool, QuitTool
        )

        registry.register("slice", SliceTool, self._agent_slice)
        registry.register("preset", PresetTool, self._agent_preset)
        registry.register("open", OpenTool, self._agent_open)
        registry.register("markers", MarkersTool, self._agent_markers)
        registry.register("set", SetTool, self._agent_set)
        registry.register("tempo", TempoTool, self._agent_tempo)
        registry.register("play", PlayTool, self._agent_play)
        registry.register("stop", StopTool, self._agent_stop)
        registry.register("export", ExportTool, self._agent_export)
        registry.register("zoom", ZoomTool, self._agent_zoom)
        registry.register("mode", ModeTool, self._agent_mode)
        registry.register("help", HelpTool, self._agent_help)
        registry.register("presets", PresetsTool, self._agent_presets)
        registry.register("quit", QuitTool, self._agent_quit)

    # Agent tool handlers
    def _agent_slice(self, args) -> str:
        if not self.model:
            return "No audio loaded"
        if args.clear:
            self._on_slice(None, None)
            return "Cleared all slices"
        self._on_slice(args.measures, args.transients)
        if args.measures:
            return f"Sliced by {args.measures} measures"
        elif args.transients is not None:
            num_segs = len(self.segment_manager.get_boundaries()) - 1
            return f"Found {num_segs} transients"
        return "Sliced"

    def _agent_preset(self, args) -> str:
        self._on_preset(args.preset_id)
        # Return the current status which was set by _on_preset
        return self._status

    def _agent_open(self, args) -> str:
        self._on_open(args.filepath, args.preset)
        if args.preset:
            return f"Loaded preset: {args.preset}"
        elif args.filepath:
            return f"Loaded: {args.filepath}"
        return "No file or preset specified"

    def _agent_markers(self, args) -> str:
        if args.reset:
            self._on_markers(None, None)
            return "Reset markers to full file"
        self._on_markers(args.start, args.end)
        return f"Markers set: L={args.start:.2f}s R={args.end:.2f}s"

    def _agent_set(self, args) -> str:
        return self._on_set(args.setting, args.value)

    def _agent_tempo(self, args) -> str:
        self._on_tempo(args.bpm, args.measures)
        if args.measures:
            return f"Tempo calculated from {args.measures} measures"
        elif args.bpm:
            return f"Tempo set to {args.bpm:.1f} BPM"
        return "Tempo updated"

    def _agent_play(self, args) -> str:
        pattern = args.pattern
        if pattern is None:
            boundaries = self.segment_manager.get_boundaries()
            num_segments = len(boundaries) - 1
            if num_segments < 1:
                return "No segments to play"
            pattern = list(range(1, num_segments + 1))
        self._on_play(pattern, args.loop)
        loop_str = " (looping)" if args.loop else ""
        return f"Playing pattern: {pattern}{loop_str}"

    def _agent_stop(self, args) -> str:
        self._on_stop()
        return "Stopped"

    def _agent_export(self, args) -> str:
        self._on_export(args.directory, args.format)
        return f"Exported to {args.directory}"

    def _agent_zoom(self, args) -> str:
        self._on_zoom(args.direction)
        return f"Zoomed {args.direction}"

    def _agent_mode(self, args) -> str:
        self._on_mode(args.mode)
        return f"Playback mode: {args.mode}"

    def _agent_help(self, args) -> str:
        return """Commands (use ! or / prefix):
  /slice <n>              Slice by measures
  /preset <id>            Load preset
  /presets                List presets
  /set bars <n>           Set bars
  /markers <s> <e>        Set markers
  /tempo <bpm>            Set tempo
  /play 1 2 3 4           Play pattern (1-0 for 1-10)
  /play q w e r           Play 11-14 (q-p for 11-20)
  /play 1 q --loop        Mix keys, loop pattern
  /loop                   Loop all segments
  /stop                   Stop playback
  /export <dir>           Export SFZ
  /zoom in|out            Zoom view
  /help                   Show help
  /quit                   Exit"""

    def _agent_presets(self, args) -> str:
        return self._on_presets()

    def _agent_quit(self, args) -> str:
        self.exit()
        return "Goodbye!"

    def process_agent_input(self, user_input: str) -> str:
        """Process input through the agent."""
        if not self.agent:
            return "Agent not initialized"
        response = self.agent.process(user_input)
        return response.message

    # Model initialization and handlers
    def init_model(self) -> bool:
        """Initialize the audio model."""
        try:
            self.model = WavAudioProcessor(preset_id=self.preset_id)
            self.end_marker = self.model.total_time
            self.zoom_end = self.model.total_time

            if self.model.preset_info:
                self.num_measures = self.model.preset_info.get('measures', 1)

            self.update_status(f"Loaded: {os.path.basename(self.model.filename)}")
            return True
        except SystemExit:
            self.update_status(f"Error: preset '{self.preset_id}' failed to load")
            logger.error("SystemExit while loading preset: %s", self.preset_id)
            return False
        except Exception as e:
            self.update_status(f"Error loading preset: {e}")
            logger.error("Failed to initialize model: %s", e)
            return False

    def _on_open(self, filepath: Optional[str], preset_id: Optional[str]) -> None:
        if preset_id:
            self.preset_id = preset_id
            if self.init_model():
                self.update_status(f"Loaded preset: {preset_id}")
            else:
                self.update_status(f"Failed to load preset: {preset_id}")
        elif filepath:
            try:
                if self.model:
                    self.model.set_filename(filepath)
                    self.end_marker = self.model.total_time
                    self.zoom_end = self.model.total_time
                    self.update_status(f"Loaded: {os.path.basename(filepath)}")
            except Exception as e:
                self.update_status(f"Error: {e}")
        self._update_waveform()

    def _on_slice(self, measures: Optional[int], transients: Optional[int]) -> None:
        if not self.model:
            return

        if measures is None and transients is None:
            self.segment_manager.set_audio_context(
                len(self.model.data_left), self.model.sample_rate
            )
        elif measures:
            self.model.split_by_measures(measures, measure_resolution=1)
        elif transients is not None:
            threshold = transients / 100.0
            self.model.split_by_transients(threshold)
        self._update_waveform()

    def _on_markers(self, start: Optional[float], end: Optional[float]) -> None:
        if start is None and end is None:
            self.start_marker = 0.0
            self.end_marker = self.model.total_time if self.model else 0.0
            self.update_status("Markers reset to full file")
        else:
            if start is not None:
                self.start_marker = max(0.0, start)
            if end is not None:
                max_time = self.model.total_time if self.model else float('inf')
                self.end_marker = min(end, max_time)
            self.update_status(f"Markers: L={self.start_marker:.2f}s R={self.end_marker:.2f}s")
        self._update_waveform()

    def _on_tempo(self, bpm: Optional[float], measure_count: Optional[int]) -> None:
        if not self.model:
            self.update_status("No audio loaded")
            return

        if measure_count:
            self.num_measures = measure_count
            calculated_bpm = self.model.get_tempo(measure_count)
            self.model.calculate_source_bpm(measure_count)
            self.update_status(f"Source tempo: {calculated_bpm:.1f} BPM ({measure_count} measures)")
        elif bpm:
            self.target_bpm = bpm
            self.model.set_playback_tempo(True, int(bpm))
            ratio = bpm / self.model.source_bpm if self.model.source_bpm > 0 else 1.0
            self.update_status(f"Playback tempo: {bpm:.0f} BPM (source: {self.model.source_bpm:.1f}, ratio: {ratio:.2f}x)")

    def _on_play(self, pattern: list[int], loop: bool) -> None:
        if not self.model:
            self.update_status("No audio loaded")
            return

        boundaries = self.segment_manager.get_boundaries()
        num_segments = len(boundaries) - 1

        if num_segments < 1:
            self.update_status("No segments defined. Use /slice first.")
            return

        for seg in pattern:
            if seg < 1 or seg > num_segments:
                self.update_status(f"Invalid segment {seg}. Valid range: 1-{num_segments}")
                return

        self.pattern_player.start(pattern, loop)
        loop_str = " (looping)" if loop else ""
        self.update_status(f"Playing pattern: {pattern}{loop_str}")

    def _on_stop(self) -> None:
        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()
        self.update_status("Stopped")

    def _on_presets(self) -> str:
        preset_list = config.get_preset_list()
        if not preset_list:
            return "No presets available"
        lines = ["Available presets:"]
        for preset_id, name in preset_list:
            lines.append(f"  {preset_id}: {name}")
        return "\n".join(lines)

    def _on_preset(self, preset_id: str) -> None:
        preset_info = config.get_preset_info(preset_id)
        if not preset_info:
            self.update_status(f"Unknown preset: {preset_id}")
            return

        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()

        old_preset_id = self.preset_id
        self.preset_id = preset_id

        if self.model:
            self.model.audio_engine.stop_stream()

        if self.init_model():
            self.update_status(f"Loaded preset: {preset_id}")
        else:
            self.preset_id = old_preset_id
            if self.init_model():
                self.update_status(f"Failed to load {preset_id} - restored {old_preset_id}")
            else:
                self.update_status(f"Failed to load preset: {preset_id}")
        self._update_waveform()

    def _on_export(self, directory: str, fmt: str) -> None:
        if not self.model:
            self.update_status("No audio loaded")
            return
        self.update_status(f"Export to {directory} (format: {fmt}) - not yet implemented")

    def _on_mode(self, mode: str) -> None:
        self.playback_mode = mode
        if self.model:
            from enums import PlaybackMode
            pm = PlaybackMode.LOOP if mode == "loop" else PlaybackMode.ONE_SHOT
            self.model.audio_engine.set_playback_mode(pm)
        self.update_status(f"Playback mode: {mode}")

    def _on_zoom(self, direction: str) -> None:
        if not self.model:
            return

        duration = self.zoom_end - self.zoom_start
        center = (self.zoom_start + self.zoom_end) / 2

        if direction == "in":
            new_duration = duration / 2
        else:
            new_duration = min(duration * 2, self.model.total_time)

        self.zoom_start = max(0, center - new_duration / 2)
        self.zoom_end = min(self.model.total_time, center + new_duration / 2)
        self.update_status(f"View: {self.zoom_start:.2f}s - {self.zoom_end:.2f}s")
        self._update_waveform()

    def _on_set(self, setting: str, value) -> str:
        if setting in ('bars', 'measures'):
            if not isinstance(value, int) or value < 1:
                return "Error: bars must be a positive integer"

            if not self.model:
                return "No audio loaded"

            self.num_measures = value
            self.model.calculate_source_bpm(value)
            self._update_waveform()
            return f"Set bars={value}, BPM={self.model.source_bpm:.1f}"
        else:
            return f"Unknown setting: {setting}. Available: bars"

    # UI update methods
    def _append_output(self, message: str) -> None:
        """Append a message to the output TextArea."""
        try:
            output = self.query_one("#output", TextArea)
            current = output.text
            if current:
                output.text = current + "\n" + message
            else:
                output.text = message
            # Scroll to bottom
            output.scroll_end(animate=False)
        except Exception:
            pass  # Widget may not exist yet

    def update_status(self, message: str) -> None:
        """Write a message to the output log."""
        # Avoid duplicate consecutive messages
        if message == self._status:
            return
        self._status = message
        self._append_output(message)

    def _update_waveform(self) -> None:
        """Update the waveform widget."""
        try:
            waveform = self.query_one("#waveform", WaveformWidget)
            if self.model:
                waveform.set_audio_data(self.model.data_left, self.model.sample_rate)
                waveform.filename = os.path.basename(self.model.filename)
                waveform.bpm = self.model.source_bpm
                waveform.bars = self.num_measures
                waveform.set_markers(self.start_marker, self.end_marker)
                waveform.set_view_range(self.zoom_start, self.zoom_end)

                boundaries = self.segment_manager.get_boundaries()
                slices = [b / self.model.sample_rate for b in boundaries]
                waveform.set_slices(slices)
        except Exception:
            pass  # Widget may not exist yet

    # Segment playback
    def play_segment_by_index(self, index: int) -> None:
        """Play a segment by its 1-based index."""
        if not self.model:
            self.update_status("No audio loaded")
            return

        boundaries = self.segment_manager.get_boundaries()
        if len(boundaries) < 2:
            self.update_status("No segments defined")
            return

        times = [b / self.model.sample_rate for b in boundaries]

        if index < 1 or index > len(times) - 1:
            self.update_status(f"Segment {index} out of range (1-{len(times)-1})")
            return

        start_time = times[index - 1]
        end_time = times[index]

        self.model.play_segment(start_time, end_time)
        self.update_status(f"Playing segment {index}: {start_time:.2f}s - {end_time:.2f}s")

    # Actions
    def action_play_selection(self) -> None:
        """Play the current L to R marker selection."""
        if not self.model:
            self.update_status("No audio loaded")
            return
        self.model.play_segment(self.start_marker, self.end_marker)
        self.update_status(f"Playing: {self.start_marker:.2f}s - {self.end_marker:.2f}s")

    def action_stop(self) -> None:
        """Stop playback."""
        self._on_stop()

    # Event handlers
    def on_command_input_segment_key_pressed(self, event: CommandInput.SegmentKeyPressed) -> None:
        """Handle segment key pressed from CommandInput."""
        if event.key in SEGMENT_KEYS:
            self.play_segment_by_index(SEGMENT_KEYS[event.key])

    def on_input_submitted(self, event) -> None:
        """Handle command submission from Input widget."""
        command = event.value.strip()
        if not command:
            return
        if command.startswith('/') or command.startswith('!'):
            result = self.process_agent_input(command)
            self.update_status(result)
        else:
            self.update_status(f"Unknown input. Use /help for commands.")
        # Clear the input
        event.input.value = ""

    def on_unmount(self) -> None:
        """Cleanup on exit."""
        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()
            self.model.audio_engine.stop_stream()


def main():
    """Entry point for TUI application."""
    import argparse

    parser = argparse.ArgumentParser(description='RCY TUI - Terminal Interface for Breakbeat Slicing')
    parser.add_argument('--preset', '-p', default='amen_classic',
                        help='Initial preset to load (default: amen_classic)')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable debug logging')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    app = RCYApp(preset_id=args.preset)
    app.run()


if __name__ == '__main__':
    main()
