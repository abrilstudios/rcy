"""TUI Application - Main event loop for RCY Terminal Interface.

A command-line interface for RCY breakbeat slicer with:
- ASCII waveform display
- Keyboard-driven segment playback (1-0, q-p keys)
- Command input (/open, /slice, /export, etc.)
"""

import sys
import os
import curses
import numpy as np
import threading
import time
from typing import Optional
import logging

from audio_processor import WavAudioProcessor
from segment_manager import get_segment_manager
from config_manager import config
from tui.waveform import render_waveform, format_display
from tui.commands import parse_command, CommandHandler, CommandType

logger = logging.getLogger(__name__)


class CommandHistory:
    """Manages command history with navigation and search."""

    def __init__(self, max_size: int = 100):
        self.history: list[str] = []
        self.max_size = max_size
        self.position = 0  # Current position in history (0 = newest)
        self.search_mode = False
        self.search_query = ""
        self.search_results: list[int] = []  # Indices of matching history entries
        self.search_index = 0  # Current position in search results

    def add(self, command: str) -> None:
        """Add a command to history."""
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
            if len(self.history) > self.max_size:
                self.history.pop(0)
        self.reset_position()

    def reset_position(self) -> None:
        """Reset navigation position to end of history."""
        self.position = len(self.history)
        self.search_mode = False
        self.search_query = ""
        self.search_results = []
        self.search_index = 0

    def navigate_up(self) -> Optional[str]:
        """Navigate to previous (older) command."""
        if not self.history:
            return None
        if self.position > 0:
            self.position -= 1
        return self.history[self.position] if self.position < len(self.history) else None

    def navigate_down(self) -> Optional[str]:
        """Navigate to next (newer) command."""
        if not self.history:
            return None
        if self.position < len(self.history):
            self.position += 1
        if self.position >= len(self.history):
            return ""  # Return empty for new command
        return self.history[self.position]

    def start_search(self) -> None:
        """Enter search mode."""
        self.search_mode = True
        self.search_query = ""
        self.search_results = []
        self.search_index = 0

    def update_search(self, query: str) -> Optional[str]:
        """Update search query and return first match."""
        self.search_query = query
        if not query:
            self.search_results = []
            return None

        # Find all matching entries (search from newest to oldest)
        self.search_results = [
            i for i in range(len(self.history) - 1, -1, -1)
            if query.lower() in self.history[i].lower()
        ]
        self.search_index = 0

        if self.search_results:
            return self.history[self.search_results[0]]
        return None

    def search_next(self) -> Optional[str]:
        """Get next search result (older match)."""
        if not self.search_results:
            return None
        if self.search_index < len(self.search_results) - 1:
            self.search_index += 1
        return self.history[self.search_results[self.search_index]]

    def search_prev(self) -> Optional[str]:
        """Get previous search result (newer match)."""
        if not self.search_results:
            return None
        if self.search_index > 0:
            self.search_index -= 1
        return self.history[self.search_results[self.search_index]]

    def accept_search(self) -> Optional[str]:
        """Accept current search result and exit search mode."""
        result = None
        if self.search_results:
            result = self.history[self.search_results[self.search_index]]
        self.search_mode = False
        return result

    def cancel_search(self) -> None:
        """Cancel search mode."""
        self.search_mode = False
        self.search_query = ""
        self.search_results = []


class PatternPlayer:
    """Plays a pattern of segments with optional looping."""

    def __init__(self, app: 'TUIApp'):
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
        while not self._stop_event.is_set():
            if not self.pattern:
                break

            segment_index = self.pattern[self.current_index]

            # Get segment boundaries
            boundaries = self.app.segment_manager.get_boundaries()
            if len(boundaries) < 2:
                break

            times = [b / self.app.model.sample_rate for b in boundaries]

            if segment_index < 1 or segment_index > len(times) - 1:
                # Invalid segment, skip
                self.current_index = (self.current_index + 1) % len(self.pattern)
                continue

            start_time = times[segment_index - 1]
            end_time = times[segment_index]
            duration = end_time - start_time

            # Adjust duration for tempo if enabled
            if self.app.model.playback_tempo_enabled and self.app.model.source_bpm > 0:
                ratio = self.app.model.target_bpm / self.app.model.source_bpm
                duration = duration / ratio

            # Update status
            self.app.status_message = f"Pattern [{self.current_index + 1}/{len(self.pattern)}]: seg {segment_index}"

            # Play the segment
            self.app.model.play_segment(start_time, end_time)

            # Wait for segment to finish (with polling for stop)
            sleep_time = duration
            sleep_step = 0.05  # Poll every 50ms
            while sleep_time > 0 and not self._stop_event.is_set():
                time.sleep(min(sleep_step, sleep_time))
                sleep_time -= sleep_step

            if self._stop_event.is_set():
                break

            # Advance to next segment
            self.current_index += 1
            if self.current_index >= len(self.pattern):
                if self.loop:
                    self.current_index = 0
                else:
                    break

        self.playing = False
        self.app.status_message = "Pattern finished"

# Key mappings for segment playback
SEGMENT_KEYS = {
    ord('1'): 1, ord('2'): 2, ord('3'): 3, ord('4'): 4, ord('5'): 5,
    ord('6'): 6, ord('7'): 7, ord('8'): 8, ord('9'): 9, ord('0'): 10,
    ord('q'): 11, ord('w'): 12, ord('e'): 13, ord('r'): 14, ord('t'): 15,
    ord('y'): 16, ord('u'): 17, ord('i'): 18, ord('o'): 19, ord('p'): 20,
}


class TUIApp:
    """Main TUI application class."""

    def __init__(self, preset_id: str = 'amen_classic'):
        """Initialize the TUI application.

        Args:
            preset_id: Initial preset to load
        """
        self.model: Optional[WavAudioProcessor] = None
        self.segment_manager = get_segment_manager()
        self.preset_id = preset_id

        # View state
        self.start_marker = 0.0
        self.end_marker = 0.0
        self.zoom_start = 0.0
        self.zoom_end = 0.0
        self.num_measures = 1
        self.playback_mode = "loop"
        self.target_bpm: Optional[float] = None  # Adjusted playback tempo

        # Pattern player
        self.pattern_player = PatternPlayer(self)

        # Command history
        self.command_history = CommandHistory()

        # Status message
        self.status_message = "Welcome to RCY TUI. Type /help for commands."

        # Running state
        self.running = True

        # Curses screen
        self.stdscr = None

    def init_model(self) -> bool:
        """Initialize the audio model."""
        try:
            self.model = WavAudioProcessor(preset_id=self.preset_id)
            self.end_marker = self.model.total_time
            self.zoom_end = self.model.total_time

            # Get measures from preset info
            if self.model.preset_info:
                self.num_measures = self.model.preset_info.get('measures', 1)

            self.status_message = f"Loaded: {os.path.basename(self.model.filename)}"
            return True
        except Exception as e:
            self.status_message = f"Error loading preset: {e}"
            logger.error("Failed to initialize model: %s", e)
            return False

    def _on_open(self, filepath: Optional[str], preset_id: Optional[str]) -> None:
        """Handle /open command."""
        if preset_id:
            self.preset_id = preset_id
            if self.init_model():
                self.status_message = f"Loaded preset: {preset_id}"
            else:
                self.status_message = f"Failed to load preset: {preset_id}"
        elif filepath:
            try:
                if self.model:
                    self.model.set_filename(filepath)
                    self.end_marker = self.model.total_time
                    self.zoom_end = self.model.total_time
                    self.status_message = f"Loaded: {os.path.basename(filepath)}"
            except Exception as e:
                self.status_message = f"Error: {e}"

    def _on_slice(self, measures: Optional[int], transients: Optional[int]) -> None:
        """Handle /slice command."""
        if not self.model:
            self.status_message = "No audio loaded"
            return

        if measures is None and transients is None:
            # Clear slices
            self.segment_manager.set_audio_context(
                len(self.model.data_left), self.model.sample_rate
            )
            self.status_message = "Cleared all slices"
        elif measures:
            self.model.split_by_measures(measures, measure_resolution=1)
            self.status_message = f"Sliced by {measures} measures"
        elif transients is not None:
            threshold = transients / 100.0  # Convert 0-100 to 0-1
            self.model.split_by_transients(threshold)
            num_segs = len(self.segment_manager.get_boundaries()) - 1
            self.status_message = f"Found {num_segs} transients"

    def _on_markers(self, start: Optional[float], end: Optional[float]) -> None:
        """Handle /markers command."""
        if start is None and end is None:
            # Reset markers
            self.start_marker = 0.0
            self.end_marker = self.model.total_time if self.model else 0.0
            self.status_message = "Markers reset to full file"
        else:
            if start is not None:
                self.start_marker = max(0.0, start)
            if end is not None:
                max_time = self.model.total_time if self.model else float('inf')
                self.end_marker = min(end, max_time)
            self.status_message = f"Markers: L={self.start_marker:.2f}s R={self.end_marker:.2f}s"

    def _on_tempo(self, bpm: Optional[float], measure_count: Optional[int]) -> None:
        """Handle /tempo command.

        /tempo <bpm> - Set adjusted playback tempo
        /tempo --measures <n> - Calculate source tempo from measures
        """
        if not self.model:
            self.status_message = "No audio loaded"
            return

        if measure_count:
            # Calculate source tempo from measures
            self.num_measures = measure_count
            calculated_bpm = self.model.get_tempo(measure_count)
            self.model.calculate_source_bpm(measure_count)
            self.status_message = f"Source tempo: {calculated_bpm:.1f} BPM ({measure_count} measures)"
        elif bpm:
            # Set adjusted playback tempo
            self.target_bpm = bpm
            self.model.set_playback_tempo(True, int(bpm))
            ratio = bpm / self.model.source_bpm if self.model.source_bpm > 0 else 1.0
            self.status_message = f"Playback tempo: {bpm:.0f} BPM (source: {self.model.source_bpm:.1f}, ratio: {ratio:.2f}x)"

    def _on_play(self, pattern: list[int], loop: bool) -> None:
        """Handle /play command."""
        if not self.model:
            self.status_message = "No audio loaded"
            return

        boundaries = self.segment_manager.get_boundaries()
        num_segments = len(boundaries) - 1

        if num_segments < 1:
            self.status_message = "No segments defined. Use /slice first."
            return

        # Validate pattern
        for seg in pattern:
            if seg < 1 or seg > num_segments:
                self.status_message = f"Invalid segment {seg}. Valid range: 1-{num_segments}"
                return

        self.pattern_player.start(pattern, loop)
        loop_str = " (looping)" if loop else ""
        self.status_message = f"Playing pattern: {pattern}{loop_str}"

    def _on_stop(self) -> None:
        """Handle /stop command."""
        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()
        self.status_message = "Stopped"

    def _on_presets(self) -> str:
        """Handle /presets command - list all available presets."""
        preset_list = config.get_preset_list()
        if not preset_list:
            return "No presets available"

        lines = ["Available presets:"]
        for preset_id, name in preset_list:
            lines.append(f"  {preset_id}: {name}")
        return "\n".join(lines)

    def _on_preset(self, preset_id: str) -> None:
        """Handle /preset command - load a preset."""
        # Stop any current playback
        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()
            self.model.audio_engine.stop_stream()

        # Load the new preset
        self.preset_id = preset_id
        if self.init_model():
            self.status_message = f"Loaded preset: {preset_id}"
        else:
            self.status_message = f"Failed to load preset: {preset_id}"

    def _on_export(self, directory: str, fmt: str) -> None:
        """Handle /export command."""
        if not self.model:
            self.status_message = "No audio loaded"
            return

        # TODO: Implement export functionality
        self.status_message = f"Export to {directory} (format: {fmt}) - not yet implemented"

    def _on_mode(self, mode: str) -> None:
        """Handle /mode command."""
        self.playback_mode = mode
        if self.model:
            from enums import PlaybackMode
            pm = PlaybackMode.LOOP if mode == "loop" else PlaybackMode.ONE_SHOT
            self.model.audio_engine.set_playback_mode(pm)
        self.status_message = f"Playback mode: {mode}"

    def _on_zoom(self, direction: str) -> None:
        """Handle /zoom command."""
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
        self.status_message = f"View: {self.zoom_start:.2f}s - {self.zoom_end:.2f}s"

    def _on_quit(self) -> None:
        """Handle /quit command."""
        self.running = False

    def play_segment_by_index(self, index: int) -> None:
        """Play a segment by its 1-based index."""
        if not self.model:
            self.status_message = "No audio loaded"
            return

        boundaries = self.segment_manager.get_boundaries()
        if len(boundaries) < 2:
            self.status_message = "No segments defined"
            return

        # Convert sample boundaries to time
        times = [b / self.model.sample_rate for b in boundaries]

        if index < 1 or index > len(times) - 1:
            self.status_message = f"Segment {index} out of range (1-{len(times)-1})"
            return

        start_time = times[index - 1]
        end_time = times[index]

        self.model.play_segment(start_time, end_time)
        self.status_message = f"Playing segment {index}: {start_time:.2f}s - {end_time:.2f}s"

    def play_selection(self) -> None:
        """Play the current L to R marker selection."""
        if not self.model:
            self.status_message = "No audio loaded"
            return

        self.model.play_segment(self.start_marker, self.end_marker)
        self.status_message = f"Playing: {self.start_marker:.2f}s - {self.end_marker:.2f}s"

    def stop_playback(self) -> None:
        """Stop current playback."""
        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()
            self.status_message = "Stopped"

    def render(self) -> list[str]:
        """Render the current display state."""
        if not self.model:
            return ["No audio loaded. Use /open <file> or /open --preset <name>"]

        # Get slice positions in seconds
        boundaries = self.segment_manager.get_boundaries()
        slices = [b / self.model.sample_rate for b in boundaries]

        # Render waveform
        waveform_lines = render_waveform(
            audio_data=self.model.data_left,
            width=70,
            height=2,
            sample_rate=self.model.sample_rate,
            start_time=self.zoom_start,
            end_time=self.zoom_end,
            slices=slices,
            start_marker=self.start_marker,
            end_marker=self.end_marker,
        )

        # Format complete display
        num_slices = max(0, len(slices) - 1)
        display = format_display(
            filename=os.path.basename(self.model.filename),
            bpm=self.model.source_bpm,
            bars=self.num_measures,
            num_slices=num_slices,
            waveform_lines=waveform_lines,
            width=72,
        )

        return display.split('\n')

    def handle_key(self, key: int) -> bool:
        """Handle a single keypress.

        Returns:
            True if key was handled, False otherwise
        """
        # Segment playback keys
        if key in SEGMENT_KEYS:
            self.play_segment_by_index(SEGMENT_KEYS[key])
            return True

        # Space - play selection
        if key == ord(' '):
            self.play_selection()
            return True

        # Escape - stop playback
        if key == 27:  # ESC
            self.stop_playback()
            return True

        return False

    def run_curses(self, stdscr) -> None:
        """Main curses event loop."""
        self.stdscr = stdscr
        curses.curs_set(1)  # Show cursor
        stdscr.timeout(100)  # Non-blocking input with 100ms timeout

        # Initialize model
        if not self.init_model():
            self.status_message = "Failed to load default preset. Use /open --preset <name>"

        # Create command handler
        handler = CommandHandler(
            on_open=self._on_open,
            on_slice=self._on_slice,
            on_markers=self._on_markers,
            on_tempo=self._on_tempo,
            on_play=self._on_play,
            on_stop=self._on_stop,
            on_presets=self._on_presets,
            on_preset=self._on_preset,
            on_export=self._on_export,
            on_mode=self._on_mode,
            on_zoom=self._on_zoom,
            on_quit=self._on_quit,
        )

        command_buffer = ""
        in_command_mode = False
        in_search_mode = False
        search_buffer = ""
        search_match = ""

        while self.running:
            # Clear and render
            stdscr.clear()
            height, width = stdscr.getmaxyx()

            # Render waveform display
            lines = self.render()
            for i, line in enumerate(lines):
                if i < height - 3:
                    try:
                        stdscr.addstr(i, 0, line[:width-1])
                    except curses.error:
                        pass

            # Status line
            status_y = min(len(lines) + 1, height - 2)
            try:
                stdscr.addstr(status_y, 0, self.status_message[:width-1])
            except curses.error:
                pass

            # Command line
            cmd_y = height - 1
            if in_search_mode:
                # Show search prompt with current match
                if search_match:
                    prompt = f"(reverse-i-search)`{search_buffer}': {search_match}"
                else:
                    prompt = f"(reverse-i-search)`{search_buffer}': "
            elif in_command_mode:
                prompt = f":{command_buffer}"
            else:
                prompt = "/ cmd, 1-0/q-p play, Space sel, ^R search"
            try:
                stdscr.addstr(cmd_y, 0, prompt[:width-1])
            except curses.error:
                pass

            stdscr.refresh()

            # Get input
            try:
                key = stdscr.getch()
            except curses.error:
                continue

            if key == -1:
                continue

            # Handle search mode
            if in_search_mode:
                if key == 27:  # ESC - cancel search
                    in_search_mode = False
                    self.command_history.cancel_search()
                    search_buffer = ""
                    search_match = ""
                elif key in (curses.KEY_ENTER, 10, 13):  # Enter - accept search result
                    result = self.command_history.accept_search()
                    if result:
                        command_buffer = result
                        in_command_mode = True
                    in_search_mode = False
                    search_buffer = ""
                    search_match = ""
                elif key == 18:  # Ctrl-R - next match (older)
                    match = self.command_history.search_next()
                    if match:
                        search_match = match
                elif key == 19:  # Ctrl-S - prev match (newer)
                    match = self.command_history.search_prev()
                    if match:
                        search_match = match
                elif key == curses.KEY_BACKSPACE or key == 127:
                    if search_buffer:
                        search_buffer = search_buffer[:-1]
                        match = self.command_history.update_search(search_buffer)
                        search_match = match or ""
                elif 32 <= key <= 126:  # Printable ASCII
                    search_buffer += chr(key)
                    match = self.command_history.update_search(search_buffer)
                    search_match = match or ""
                continue

            # Handle command mode
            if in_command_mode:
                if key == 27:  # ESC - cancel command
                    in_command_mode = False
                    command_buffer = ""
                    self.command_history.reset_position()
                elif key in (curses.KEY_ENTER, 10, 13):  # Enter - execute command
                    if command_buffer:
                        self.command_history.add(command_buffer)
                        cmd = parse_command("/" + command_buffer)
                        result = handler.execute(cmd)
                        self.status_message = result
                    in_command_mode = False
                    command_buffer = ""
                elif key == curses.KEY_UP:  # Up arrow - previous command
                    prev_cmd = self.command_history.navigate_up()
                    if prev_cmd is not None:
                        command_buffer = prev_cmd
                elif key == curses.KEY_DOWN:  # Down arrow - next command
                    next_cmd = self.command_history.navigate_down()
                    if next_cmd is not None:
                        command_buffer = next_cmd
                elif key == 18:  # Ctrl-R - start search
                    in_search_mode = True
                    self.command_history.start_search()
                    search_buffer = ""
                    search_match = ""
                elif key == curses.KEY_BACKSPACE or key == 127:
                    command_buffer = command_buffer[:-1]
                elif 32 <= key <= 126:  # Printable ASCII
                    command_buffer += chr(key)
            else:
                if key == ord('/'):
                    in_command_mode = True
                    command_buffer = ""
                    self.command_history.reset_position()
                elif key == 18:  # Ctrl-R - start search from normal mode
                    in_command_mode = True
                    in_search_mode = True
                    self.command_history.start_search()
                    search_buffer = ""
                    search_match = ""
                else:
                    self.handle_key(key)

        # Cleanup
        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()
            self.model.audio_engine.stop_stream()

    def run(self) -> None:
        """Run the TUI application."""
        try:
            curses.wrapper(self.run_curses)
        except Exception as e:
            # Print error after curses cleanup so it's visible
            import traceback
            print(f"\nTUI Error: {e}")
            traceback.print_exc()


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

    app = TUIApp(preset_id=args.preset)
    app.run()


if __name__ == '__main__':
    main()
