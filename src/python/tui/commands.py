"""Command parser for TUI interface."""

import shlex
from dataclasses import dataclass
from typing import Optional, Callable, Any
from enum import Enum


class CommandType(Enum):
    """Types of TUI commands."""
    OPEN = "open"
    SLICE = "slice"
    MARKERS = "markers"
    TEMPO = "tempo"
    PLAY = "play"
    STOP = "stop"
    PRESETS = "presets"
    PRESET = "preset"
    EXPORT = "export"
    MODE = "mode"
    ZOOM = "zoom"
    HELP = "help"
    QUIT = "quit"
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    """Result of parsing a command string."""
    cmd_type: CommandType
    args: list[str]
    options: dict[str, Any]
    error: Optional[str] = None


def parse_command(input_str: str) -> ParsedCommand:
    """Parse a command string into structured form.

    Commands start with / and may have positional args and --options.

    Examples:
        /open jungle.wav
        /slice --measures 4
        /slice --transients 60
        /export /tmp/output
        /markers 0.5 3.2
        /tempo 140
        /tempo --measures 4
        /play [1,4,2,3]
        /play --loop [1,4,2,3]
        /stop
        /mode loop
        /zoom in
        /zoom out
        /help
        /quit

    Args:
        input_str: Raw command string

    Returns:
        ParsedCommand with type, args, options, and optional error
    """
    input_str = input_str.strip()

    if not input_str.startswith("/"):
        return ParsedCommand(
            cmd_type=CommandType.UNKNOWN,
            args=[],
            options={},
            error="Commands must start with /"
        )

    # Remove leading /
    input_str = input_str[1:]

    try:
        tokens = shlex.split(input_str)
    except ValueError as e:
        return ParsedCommand(
            cmd_type=CommandType.UNKNOWN,
            args=[],
            options={},
            error=f"Parse error: {e}"
        )

    if not tokens:
        return ParsedCommand(
            cmd_type=CommandType.UNKNOWN,
            args=[],
            options={},
            error="Empty command"
        )

    cmd_name = tokens[0].lower()
    tokens = tokens[1:]

    # Map command names
    cmd_map = {
        "open": CommandType.OPEN,
        "o": CommandType.OPEN,
        "slice": CommandType.SLICE,
        "s": CommandType.SLICE,
        "markers": CommandType.MARKERS,
        "m": CommandType.MARKERS,
        "tempo": CommandType.TEMPO,
        "t": CommandType.TEMPO,
        "play": CommandType.PLAY,
        "p": CommandType.PLAY,
        "stop": CommandType.STOP,
        "x": CommandType.STOP,
        "presets": CommandType.PRESETS,
        "preset": CommandType.PRESET,
        "export": CommandType.EXPORT,
        "e": CommandType.EXPORT,
        "mode": CommandType.MODE,
        "zoom": CommandType.ZOOM,
        "z": CommandType.ZOOM,
        "help": CommandType.HELP,
        "h": CommandType.HELP,
        "?": CommandType.HELP,
        "quit": CommandType.QUIT,
        "q": CommandType.QUIT,
        "exit": CommandType.QUIT,
    }

    cmd_type = cmd_map.get(cmd_name, CommandType.UNKNOWN)
    if cmd_type == CommandType.UNKNOWN:
        return ParsedCommand(
            cmd_type=CommandType.UNKNOWN,
            args=[],
            options={},
            error=f"Unknown command: {cmd_name}"
        )

    # Parse args and options
    args = []
    options = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            opt_name = token[2:]
            # Check if next token is the value
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                opt_value = tokens[i + 1]
                # Try to convert to number
                try:
                    if "." in opt_value:
                        opt_value = float(opt_value)
                    else:
                        opt_value = int(opt_value)
                except ValueError:
                    pass
                options[opt_name] = opt_value
                i += 2
            else:
                # Flag option (boolean)
                options[opt_name] = True
                i += 1
        else:
            args.append(token)
            i += 1

    return ParsedCommand(cmd_type=cmd_type, args=args, options=options)


class CommandHandler:
    """Handles execution of parsed commands."""

    def __init__(
        self,
        on_open: Callable[[str, Optional[str]], None],
        on_slice: Callable[[Optional[int], Optional[int]], None],
        on_markers: Callable[[Optional[float], Optional[float]], None],
        on_tempo: Callable[[Optional[float], Optional[int]], None],
        on_play: Callable[[list[int], bool], None],
        on_stop: Callable[[], None],
        on_presets: Callable[[], str],
        on_preset: Callable[[str], None],
        on_export: Callable[[str, str], None],
        on_mode: Callable[[str], None],
        on_zoom: Callable[[str], None],
        on_quit: Callable[[], None],
    ):
        """Initialize command handler with callbacks.

        Args:
            on_open: Called with (filepath, preset_id)
            on_slice: Called with (measures, transient_threshold)
            on_markers: Called with (start, end) - None means reset
            on_tempo: Called with (bpm, measure_count)
            on_play: Called with (pattern, loop) - pattern is list of segment indices
            on_stop: Called to stop playback
            on_presets: Called to list all presets, returns formatted string
            on_preset: Called with (preset_id) to load a preset
            on_export: Called with (directory, format)
            on_mode: Called with mode string ("loop" or "oneshot")
            on_zoom: Called with direction ("in" or "out")
            on_quit: Called when user wants to exit
        """
        self.on_open = on_open
        self.on_slice = on_slice
        self.on_markers = on_markers
        self.on_tempo = on_tempo
        self.on_play = on_play
        self.on_stop = on_stop
        self.on_presets = on_presets
        self.on_preset = on_preset
        self.on_export = on_export
        self.on_mode = on_mode
        self.on_zoom = on_zoom
        self.on_quit = on_quit

    def execute(self, cmd: ParsedCommand) -> str:
        """Execute a parsed command.

        Args:
            cmd: Parsed command

        Returns:
            Status message to display
        """
        if cmd.error:
            return f"Error: {cmd.error}"

        try:
            match cmd.cmd_type:
                case CommandType.OPEN:
                    return self._handle_open(cmd)
                case CommandType.SLICE:
                    return self._handle_slice(cmd)
                case CommandType.MARKERS:
                    return self._handle_markers(cmd)
                case CommandType.TEMPO:
                    return self._handle_tempo(cmd)
                case CommandType.PLAY:
                    return self._handle_play(cmd)
                case CommandType.STOP:
                    return self._handle_stop(cmd)
                case CommandType.PRESETS:
                    return self._handle_presets(cmd)
                case CommandType.PRESET:
                    return self._handle_preset(cmd)
                case CommandType.EXPORT:
                    return self._handle_export(cmd)
                case CommandType.MODE:
                    return self._handle_mode(cmd)
                case CommandType.ZOOM:
                    return self._handle_zoom(cmd)
                case CommandType.HELP:
                    return self._handle_help()
                case CommandType.QUIT:
                    self.on_quit()
                    return "Goodbye!"
                case _:
                    return f"Unknown command type: {cmd.cmd_type}"
        except Exception as e:
            return f"Error: {e}"

    def _handle_open(self, cmd: ParsedCommand) -> str:
        preset = cmd.options.get("preset")
        if preset:
            self.on_open(None, preset)
            return f"Loaded preset: {preset}"
        elif cmd.args:
            filepath = cmd.args[0]
            self.on_open(filepath, None)
            return f"Loaded: {filepath}"
        else:
            return "Usage: /open <file.wav> or /open --preset <name>"

    def _handle_slice(self, cmd: ParsedCommand) -> str:
        if cmd.options.get("clear"):
            self.on_slice(None, None)
            return "Cleared all slices"

        measures = cmd.options.get("measures")
        transients = cmd.options.get("transients")

        if measures:
            self.on_slice(measures, None)
            return f"Sliced by measures: {measures}"
        elif transients is not None:
            self.on_slice(None, transients)
            return f"Sliced by transients (threshold: {transients})"
        else:
            return "Usage: /slice --measures <n> or /slice --transients <0-100>"

    def _handle_markers(self, cmd: ParsedCommand) -> str:
        if cmd.options.get("reset"):
            self.on_markers(None, None)
            return "Reset markers to full file"

        if len(cmd.args) >= 2:
            try:
                start = float(cmd.args[0])
                end = float(cmd.args[1])
                self.on_markers(start, end)
                return f"Markers set: L={start:.2f}s R={end:.2f}s"
            except ValueError:
                return "Error: Markers must be numbers (seconds)"
        else:
            return "Usage: /markers <start> <end> or /markers --reset"

    def _handle_tempo(self, cmd: ParsedCommand) -> str:
        measures = cmd.options.get("measures")
        if measures:
            self.on_tempo(None, measures)
            return f"Tempo calculated from {measures} measures"

        if cmd.args:
            try:
                bpm = float(cmd.args[0])
                self.on_tempo(bpm, None)
                return f"Tempo set to {bpm:.1f} BPM"
            except ValueError:
                return "Error: BPM must be a number"

        return "Usage: /tempo <bpm> or /tempo --measures <n>"

    def _handle_play(self, cmd: ParsedCommand) -> str:
        loop = "loop" in cmd.options

        # Pattern can be in args or as value of --loop option
        pattern_str = None
        if cmd.args:
            pattern_str = cmd.args[0]
        elif loop and isinstance(cmd.options.get("loop"), str):
            pattern_str = cmd.options["loop"]

        if not pattern_str:
            return "Usage: /play [1,2,3,4] or /play --loop [1,4,2,3]"

        # Remove brackets and parse numbers
        pattern_str = pattern_str.strip("[]")
        try:
            pattern = [int(x.strip()) for x in pattern_str.split(",")]
        except ValueError:
            return "Error: Pattern must be comma-separated integers, e.g. [1,2,3,4]"

        if not pattern:
            return "Error: Empty pattern"

        self.on_play(pattern, loop)
        loop_str = " (looping)" if loop else ""
        return f"Playing pattern: {pattern}{loop_str}"

    def _handle_stop(self, cmd: ParsedCommand) -> str:
        self.on_stop()
        return "Stopped"

    def _handle_presets(self, cmd: ParsedCommand) -> str:
        return self.on_presets()

    def _handle_preset(self, cmd: ParsedCommand) -> str:
        if not cmd.args:
            return "Usage: /preset <preset_id>"
        preset_id = cmd.args[0]
        self.on_preset(preset_id)
        return f"Loading preset: {preset_id}"

    def _handle_export(self, cmd: ParsedCommand) -> str:
        if not cmd.args:
            return "Usage: /export <directory> [--format wav|flac]"

        directory = cmd.args[0]
        fmt = cmd.options.get("format", "wav")
        self.on_export(directory, fmt)
        return f"Exported to {directory} (format: {fmt})"

    def _handle_mode(self, cmd: ParsedCommand) -> str:
        if not cmd.args:
            return "Usage: /mode loop|oneshot"

        mode = cmd.args[0].lower()
        if mode not in ("loop", "oneshot"):
            return "Mode must be 'loop' or 'oneshot'"

        self.on_mode(mode)
        return f"Playback mode: {mode}"

    def _handle_zoom(self, cmd: ParsedCommand) -> str:
        if not cmd.args:
            return "Usage: /zoom in|out"

        direction = cmd.args[0].lower()
        if direction not in ("in", "out"):
            return "Zoom direction must be 'in' or 'out'"

        self.on_zoom(direction)
        return f"Zoomed {direction}"

    def _handle_help(self) -> str:
        return """Commands:
  /open <file.wav>          Load audio file
  /presets                  List available presets
  /preset <id>              Load preset by ID
  /slice --measures <n>     Slice by measure count
  /slice --transients <n>   Slice by transients (0-100)
  /slice --clear            Clear all slices
  /markers <start> <end>    Set L/R markers (seconds)
  /markers --reset          Reset markers to full file
  /tempo <bpm>              Set adjusted playback tempo
  /tempo --measures <n>     Calculate source tempo from measures
  /play [1,2,3,4]           Play pattern once
  /play --loop [1,4,2,3]    Play pattern looping
  /stop                     Stop playback
  /export <dir>             Export SFZ + samples
  /mode loop|oneshot        Set single-segment playback mode
  /zoom in|out              Zoom view
  /help                     Show this help
  /quit                     Exit

Playback keys:
  1-0       Play segments 1-10
  q-p       Play segments 11-20
  Space     Play selection (L to R)
  Escape    Stop playback"""
