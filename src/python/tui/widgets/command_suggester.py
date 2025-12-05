"""Context-aware tab completion for slash commands."""

from textual.suggester import Suggester

from tui.agents.tools import TOOL_SCHEMAS, TOOL_ALIASES


class CommandSuggester(Suggester):
    """Suggester that provides context-aware completions for slash commands.

    Provides completions for:
    - Command names after '/' (e.g., /pre -> /preset)
    - Preset IDs after '/preset ' (e.g., /preset rl_ -> /preset rl_hot_pants)
    - Bank letters after '/ep133_upload_bank ' (A, B, C, D)
    """

    def __init__(self, config_manager=None):
        """Initialize the suggester.

        Args:
            config_manager: ConfigManager instance for accessing presets.
                           If None, preset completion is disabled.
        """
        super().__init__(use_cache=False, case_sensitive=True)
        self.config = config_manager
        # Registry of command-specific completers
        self._completers = {
            "preset": self._complete_preset,
            "ep133_upload_bank": self._complete_bank,
        }

    async def get_suggestion(self, value: str, cursor_position: int) -> str | None:
        """Get a suggestion for the current input.

        Args:
            value: Current input text
            cursor_position: Position of cursor (not currently used)

        Returns:
            Suggested completion or None if no suggestion
        """
        if not value.startswith("/"):
            return None

        # Parse input: command and optional argument
        content = value[1:]  # Remove leading /
        parts = content.split(maxsplit=1)

        if len(parts) == 0:
            # Just "/" - no suggestion yet
            return None

        if " " not in value:
            # Still typing command name (no space after command)
            return self._complete_command(parts[0])

        # Have command and space - either with argument prefix or empty
        cmd = parts[0]
        arg_prefix = parts[1] if len(parts) == 2 else ""

        if cmd in self._completers:
            return self._completers[cmd](arg_prefix)

        return None

    def _complete_command(self, prefix: str) -> str | None:
        """Complete a command name.

        Args:
            prefix: Partial command name (without /)

        Returns:
            Full command suggestion including / prefix, or None
        """
        if not prefix:
            return None

        commands = list(TOOL_SCHEMAS.keys()) + list(TOOL_ALIASES.keys())
        matches = sorted([c for c in commands if c.startswith(prefix)])

        if matches:
            return "/" + matches[0]
        return None

    def _complete_preset(self, prefix: str) -> str | None:
        """Complete a preset ID.

        Args:
            prefix: Partial preset ID

        Returns:
            Full command with preset suggestion, or None
        """
        if not self.config:
            return None

        presets = [p[0] for p in self.config.get_preset_list()]
        matches = sorted([p for p in presets if p.startswith(prefix)])

        if matches:
            return f"/preset {matches[0]}"
        return None

    def _complete_bank(self, prefix: str) -> str | None:
        """Complete an EP-133 bank letter.

        Args:
            prefix: Partial bank letter

        Returns:
            Full command with bank suggestion, or None
        """
        banks = ["A", "B", "C", "D"]
        matches = [b for b in banks if b.startswith(prefix.upper())]

        if matches:
            return f"/ep133_upload_bank {matches[0]}"
        return None
