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

# Suppress noisy HTTP client loggers early (before any imports that might trigger them)
for _logger_name in ('httpx', 'httpcore', 'openai', 'pydantic_ai'):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

from textual.app import App, ComposeResult
from textual.widgets import Static, TextArea
from textual.binding import Binding

from logging_config import setup_logging

from audio_processor import WavAudioProcessor
from segment_manager import get_segment_manager
from config_manager import config
from export_utils import ExportUtils
from tui.widgets import WaveformWidget, CommandInput, CommandSuggester
from tui.markers import MarkerManager, MarkerKind
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
        # Marker focus bindings
        Binding("[", "cycle_focus_prev", "Prev Marker", show=False),
        Binding("]", "cycle_focus_next", "Next Marker", show=False),
    ]

    def __init__(self, preset_id: str = 'amen_classic'):
        super().__init__()
        self.preset_id = preset_id
        self.model: Optional[WavAudioProcessor] = None
        self.segment_manager = get_segment_manager()

        # Marker manager - unified focus model for L/R and segment markers
        self.marker_manager = MarkerManager(
            debounce_ms=50.0,
            nudge_samples=441,  # ~10ms at 44100Hz
            min_region_samples=441,  # ~10ms minimum region
        )

        # View state (legacy - kept for compatibility, synced from marker_manager)
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
        output = TextArea(id="output", read_only=True, soft_wrap=True)
        output.can_focus = False
        yield output
        suggester = CommandSuggester(config_manager=config)
        yield CommandInput(id="command", suggester=suggester)

    def on_mount(self) -> None:
        """Initialize when app is mounted."""
        self._init_agent()
        self._append_output(self._status)
        if not self.init_model():
            self._append_output("Failed to load preset. Use /preset <name>")
        self._update_waveform()
        self.query_one("#command", CommandInput).focus()

    def _init_agent(self) -> None:
        """Initialize default agent. LLM agent is lazy-loaded on first use."""
        self._tool_registry = ToolRegistry()
        self._register_agent_tools(self._tool_registry)

        # Create default agent for fast /command processing
        self.default_agent = create_agent("default", self._tool_registry)

        # LLM agent loaded lazily on first natural language input
        self._llm_agent = None
        self._llm_agent_initialized = False

        logger.info("Initialized default agent for /commands")

    def _register_agent_tools(self, registry: ToolRegistry) -> None:
        """Register tool handlers with the agent's tool registry."""
        from tui.agents.tools import (
            SliceTool, PresetTool, OpenTool, MarkersTool,
            SetTool, TempoTool, PlayTool, StopTool, ExportTool,
            ZoomTool, ModeTool, HelpTool, PresetsTool, QuitTool, CutTool, NudgeTool,
            EP133Tool,
        )
        from tui.ep133_handler import ep133_handler

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
        registry.register("cut", CutTool, self._agent_cut)
        registry.register("nudge", NudgeTool, self._agent_nudge)

        # EP-133 unified command
        registry.register("ep133", EP133Tool, lambda args: ep133_handler(args, self))

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
  /set release <ms>       Tail decay to zero crossing (default: 3ms)
  /markers <s> <e>        Set markers
  /cut                    Cut audio to L/R region
  /nudge left|right       Nudge marker (--mode fine|coarse)
  /tempo <bpm>            Set tempo
  /play 1 2 3 4           Play pattern (1-0 for 1-10)
  /play q w e r           Play 11-14 (q-p for 11-20)
  /play 1 q --loop        Mix keys, loop pattern
  /loop                   Loop all segments
  /stop                   Stop playback
  /export <dir>           Export SFZ
  /zoom in|out            Zoom view
  /help                   Show help
  /quit                   Exit

EP-133 Commands:
  /ep133 connect        Connect to EP-133
  /ep133 disconnect     Disconnect from EP-133
  /ep133 status         Show connection status
  /ep133 list           List sounds on device
  /ep133 upload <bank>  Upload segments to bank (A/B/C/D)
  /ep133 clear <bank>   Clear pad assignments in bank"""

    def _agent_presets(self, args) -> str:
        return self._on_presets()

    def _agent_quit(self, args) -> str:
        self.exit()
        return "Goodbye!"

    def _agent_cut(self, args) -> str:
        """Handler for /cut command."""
        return self._on_cut()

    def _on_cut(self) -> str:
        """Cut audio to L/R region in-place."""
        if not self.model:
            return "No audio loaded"

        if self.start_marker >= self.end_marker:
            return "Error: L marker must be before R marker"

        old_duration = self.model.total_time
        new_duration = self.end_marker - self.start_marker

        # Use existing crop_to_time_range method
        success = self.model.crop_to_time_range(self.start_marker, self.end_marker)

        if success:
            # Reset to full file state (same as fresh load)
            self.start_marker = 0.0
            self.end_marker = self.model.total_time
            self.zoom_start = 0.0
            self.zoom_end = self.model.total_time

            # Sync marker manager with new audio context
            self.marker_manager.set_audio_context(
                len(self.model.data_left),
                self.model.sample_rate
            )

            # Clear segment cache
            self._cached_segment_times = None

            # Update display
            self._update_waveform()

            return f"Cut: {old_duration:.2f}s → {new_duration:.2f}s"
        else:
            return "Cut failed"

    def _agent_nudge(self, args) -> str:
        """Handler for /nudge command."""
        focused = self.marker_manager.focused_marker
        if not focused:
            return "No marker focused"

        base = self.marker_manager._nudge_samples
        if args.mode == "fine":
            delta = max(1, base // 10)
        elif args.mode == "coarse":
            delta = base * 3
        else:
            delta = base

        if args.direction == "left":
            delta = -delta

        if self.marker_manager.nudge_focused_marker(delta):
            self._on_marker_nudged()
            return f"[{focused.id}] moved {abs(delta)} samples"
        return "Nudge failed"

    def process_command(self, command: str) -> str:
        """Process /command through default agent (fast path)."""
        if not self.default_agent:
            return "Agent not initialized"
        response = self.default_agent.process(command)
        return response.message

    def _get_llm_agent(self):
        """Lazy-load LLM agent on first use."""
        if not self._llm_agent_initialized:
            self._llm_agent_initialized = True
            openrouter_cfg = config.get_setting("agent", "openrouter", {})
            try:
                self._llm_agent = create_agent(
                    "openrouter",
                    self._tool_registry,
                    model=openrouter_cfg.get("default_model", "anthropic/claude-sonnet-4"),
                    temperature=openrouter_cfg.get("temperature", 0.3),
                    max_tokens=openrouter_cfg.get("max_tokens", 1024),
                )
                logger.info(f"Initialized LLM agent: {self._llm_agent.name}")
            except ValueError as e:
                logger.warning(f"LLM agent not available: {e}")
                self._llm_agent = None
        return self._llm_agent

    def process_natural_language(self, text: str) -> str:
        """Process natural language through LLM agent."""
        llm_agent = self._get_llm_agent()
        if not llm_agent:
            return "LLM agent not available. Use /commands or set OPENROUTER_API_KEY."
        response = llm_agent.process(text)
        return response.message

    # Model initialization and handlers
    def init_model(self) -> bool:
        """Initialize the audio model."""
        try:
            self.model = WavAudioProcessor(preset_id=self.preset_id)
            self.end_marker = self.model.total_time
            self.zoom_end = self.model.total_time

            # Reset segment manager to single segment (full file)
            self.segment_manager.set_audio_context(
                len(self.model.data_left),
                self.model.sample_rate
            )
            # Invalidate segment cache
            self._cached_segment_times = None

            # Initialize marker manager with audio context
            self.marker_manager.set_audio_context(
                len(self.model.data_left),
                self.model.sample_rate
            )
            # Sync legacy marker values from marker_manager
            self._sync_markers_from_manager()

            if self.model.preset_info:
                self.num_measures = self.model.preset_info.get('measures', 1)

            self.update_status(f"Loaded: {os.path.basename(self.model.filename)}")
            return True
        except SystemExit:
            self.update_status(f"Error: preset '{self.preset_id}' failed to load")
            logger.warning("SystemExit while loading preset: %s", self.preset_id)
            return False
        except Exception as e:
            self.update_status(f"Error loading preset: {e}")
            logger.warning("Failed to initialize model: %s", e)
            return False

    def _sync_markers_from_manager(self) -> None:
        """Sync legacy start/end_marker from marker_manager."""
        l_marker = self.marker_manager.get_marker("L")
        r_marker = self.marker_manager.get_marker("R")
        if l_marker and self.model:
            self.start_marker = l_marker.position / self.model.sample_rate
        if r_marker and self.model:
            self.end_marker = r_marker.position / self.model.sample_rate

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
            # Pass L/R markers as region bounds
            self.model.split_by_measures(
                measures,
                measure_resolution=1,
                start_time=self.start_marker,
                end_time=self.end_marker
            )
        elif transients is not None:
            threshold = transients / 100.0
            # Pass L/R markers as region bounds for transient detection
            self.model.split_by_transients(
                threshold,
                start_time=self.start_marker,
                end_time=self.end_marker
            )

        # Sync segment boundaries to MarkerManager for unified focus/nudge
        boundaries = self.segment_manager.get_boundaries()
        self.marker_manager.sync_from_boundaries(boundaries)

        # Invalidate segment cache after slicing
        self._cached_segment_times = None
        self._update_waveform()

    def _on_markers(self, start: Optional[float], end: Optional[float]) -> None:
        if not self.model:
            return

        if start is None and end is None:
            self.start_marker = 0.0
            self.end_marker = self.model.total_time
            self.update_status("Markers reset to full file")
        else:
            if start is not None:
                self.start_marker = max(0.0, start)
            if end is not None:
                max_time = self.model.total_time
                self.end_marker = min(end, max_time)
            self.update_status(f"Markers: L={self.start_marker:.2f}s R={self.end_marker:.2f}s")

        # Sync to MarkerManager
        start_samples = int(self.start_marker * self.model.sample_rate)
        end_samples = int(self.end_marker * self.model.sample_rate)
        self.marker_manager.set_region_markers(start_samples, end_samples)

        # Remove segments outside new region
        self._remove_segments_outside_region()

        # Sync boundaries to segment_manager
        new_boundaries = self.marker_manager.get_boundaries()
        self.segment_manager.set_boundaries(new_boundaries)

        # Invalidate cache
        self._cached_segment_times = None

        self._update_waveform()

    def _on_tempo(self, bpm: Optional[float], measure_count: Optional[int]) -> None:
        if not self.model:
            self.update_status("No audio loaded")
            return

        if measure_count:
            self.num_measures = measure_count
            # Pass L/R region for tempo calculation
            calculated_bpm = self.model.get_tempo(
                measure_count,
                start_time=self.start_marker,
                end_time=self.end_marker
            )
            self.model.calculate_source_bpm(
                measure_count,
                start_time=self.start_marker,
                end_time=self.end_marker
            )
            region_duration = self.end_marker - self.start_marker
            self.update_status(
                f"Source tempo: {calculated_bpm:.1f} BPM ({measure_count} bars in {region_duration:.2f}s)"
            )
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

        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)

        try:
            stats = ExportUtils.export_segments(
                model=self.model,
                tempo=self.model.source_bpm,
                num_measures=self.num_measures,
                directory=directory,
                start_marker_pos=self.start_marker,
                end_marker_pos=self.end_marker
            )
            self.update_status(f"Exported {stats['segment_count']} segments to {directory}")
        except Exception as e:
            self.update_status(f"Export failed: {e}")

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
            # Use L/R region for tempo calculation
            self.model.calculate_source_bpm(
                value,
                start_time=self.start_marker,
                end_time=self.end_marker
            )
            self._update_waveform()
            region_duration = self.end_marker - self.start_marker
            return f"Set bars={value}, BPM={self.model.source_bpm:.1f} ({region_duration:.2f}s region)"
        elif setting == 'release':
            if not isinstance(value, (int, float)) or value < 0:
                return "Error: release must be a positive number (ms)"

            # Update config in memory
            config.set_setting("audio", "tailFade", {
                "enabled": value > 0,
                "durationMs": int(value),
                "curve": "exponential"
            })

            # Update cached config in audio engine
            if self.model:
                self.model.audio_engine.update_tail_fade_config()

            return f"Set release={value}ms"
        else:
            return f"Unknown setting: {setting}. Available: bars, release"

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
                # Set internal segment markers only (exclude L/R) for focus indication
                internal_segments = slices[1:-1] if len(slices) > 2 else []
                waveform.set_segment_markers(internal_segments)

                # Set focused marker for visual indication
                waveform.set_focused_marker(self.marker_manager.focused_marker_id)
        except Exception:
            pass  # Widget may not exist yet

    # Segment playback - optimized for low latency key response
    def play_segment_by_index(self, index: int) -> None:
        """Play a segment by its 1-based index. Optimized for fast key response."""
        if not self.model:
            return

        # Use cached segment times if available
        if not hasattr(self, '_cached_segment_times') or self._cached_segment_times is None:
            self._update_segment_cache()

        if self._cached_segment_times is None or len(self._cached_segment_times) < 2:
            return

        num_segments = len(self._cached_segment_times) - 1
        if index < 1 or index > num_segments:
            return

        start_time = self._cached_segment_times[index - 1]
        end_time = self._cached_segment_times[index]

        # Direct call to audio engine - skip status update for speed
        self.model.play_segment(start_time, end_time)

    def _update_segment_cache(self) -> None:
        """Update cached segment times for fast playback."""
        if not self.model:
            self._cached_segment_times = None
            return
        boundaries = self.segment_manager.get_boundaries()
        if len(boundaries) < 2:
            self._cached_segment_times = None
            return
        sample_rate = self.model.sample_rate
        self._cached_segment_times = [b / sample_rate for b in boundaries]

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

    def action_nudge_left(self) -> None:
        """Nudge focused marker left."""
        if self.marker_manager.nudge_left():
            self._on_marker_nudged()

    def action_nudge_right(self) -> None:
        """Nudge focused marker right."""
        if self.marker_manager.nudge_right():
            self._on_marker_nudged()

    def _on_marker_nudged(self) -> None:
        """Handle marker position change after nudge."""
        focused = self.marker_manager.focused_marker

        # Always sync for visual feedback first
        self._sync_markers_from_manager()

        if focused and focused.kind in (MarkerKind.REGION_START, MarkerKind.REGION_END):
            # L or R changed - delete segments outside new region
            self._remove_segments_outside_region()

            # Recalculate tempo for new region
            if self.num_measures > 0 and self.model:
                self.model.calculate_source_bpm(
                    self.num_measures,
                    start_time=self.start_marker,
                    end_time=self.end_marker
                )

        # Sync marker boundaries back to segment_manager for playback
        new_boundaries = self.marker_manager.get_boundaries()
        self.segment_manager.set_boundaries(new_boundaries)

        self._cached_segment_times = None  # Invalidate cache
        self._update_waveform()

    def _remove_segments_outside_region(self) -> None:
        """Delete segment markers that fall outside L/R region."""
        l_marker = self.marker_manager.get_marker("L")
        r_marker = self.marker_manager.get_marker("R")
        if not l_marker or not r_marker:
            return

        l_pos = l_marker.position
        r_pos = r_marker.position

        # Find segment markers outside the region
        to_remove = []
        for marker in self.marker_manager.get_segment_markers():
            if marker.position <= l_pos or marker.position >= r_pos:
                to_remove.append(marker.id)

        # Remove them
        for marker_id in to_remove:
            self.marker_manager.remove_segment_marker(marker_id)

    def action_cycle_focus_next(self) -> None:
        """Cycle focus to next marker (by position)."""
        if self.marker_manager.cycle_focus(reverse=False):
            self._update_waveform()

    def action_cycle_focus_prev(self) -> None:
        """Cycle focus to previous marker (by position)."""
        if self.marker_manager.cycle_focus(reverse=True):
            self._update_waveform()

    # Event handlers
    def on_command_input_segment_key_pressed(self, event: CommandInput.SegmentKeyPressed) -> None:
        """Handle segment key pressed from CommandInput."""
        if event.key in SEGMENT_KEYS:
            self.play_segment_by_index(SEGMENT_KEYS[event.key])

    def on_command_input_marker_nudge(self, event: CommandInput.MarkerNudge) -> None:
        """Handle marker nudge from CommandInput."""
        mode = getattr(event, 'mode', 'normal')

        base = self.marker_manager._nudge_samples
        if mode == "fine":
            delta = max(1, base // 10)
        elif mode == "coarse":
            delta = base * 10
        else:
            delta = base

        if event.direction == "left":
            delta = -delta

        if self.marker_manager.nudge_focused_marker(delta):
            self._on_marker_nudged()

    def on_command_input_marker_cycle_focus(self, event: CommandInput.MarkerCycleFocus) -> None:
        """Handle marker focus cycle from CommandInput."""
        if event.reverse:
            self.action_cycle_focus_prev()
        else:
            self.action_cycle_focus_next()

    def on_command_input_space_pressed(self, event: CommandInput.SpacePressed) -> None:
        """Handle space pressed in segment mode - toggle play/stop full sample."""
        if not self.model:
            return
        # Toggle: if playing, stop. Otherwise play full sample.
        if self.model.is_playing:
            self.model.stop_playback()
            self.update_status("Stopped")
        else:
            self.model.play_segment(0.0, self.model.total_time)
            self.update_status("Playing full sample")

    def on_command_input_output_scroll(self, event: CommandInput.OutputScroll) -> None:
        """Handle up/down arrow in segment mode - scroll output panel."""
        try:
            output = self.query_one("#output", TextArea)
            if event.direction == "up":
                output.scroll_relative(y=-1)
            else:
                output.scroll_relative(y=1)
        except Exception:
            pass

    def on_input_submitted(self, event) -> None:
        """Handle command submission from Input widget."""
        text = event.value.strip()
        if not text:
            return

        if text.startswith('/') or text.startswith('!'):
            # Fast path: direct command processing (no LLM)
            result = self.process_command(text)
        else:
            # Natural language: route to LLM
            result = self.process_natural_language(text)

        self.update_status(result)
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

    # Initialize centralized logging (suppresses console noise, logs to file)
    setup_logging()

    if args.debug:
        # Override console level for debug mode
        logging.getLogger().setLevel(logging.DEBUG)

    app = RCYApp(preset_id=args.preset)
    app.run()


if __name__ == '__main__':
    main()
