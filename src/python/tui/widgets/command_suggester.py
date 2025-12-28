"""Context-aware tab completion for slash commands."""

from textual.suggester import Suggester

from tui.agents.tools import TOOL_SCHEMAS, TOOL_ALIASES


class CommandSuggester(Suggester):
    """Suggester that provides context-aware completions for slash commands.

    Provides completions for:
    - Command names after '/' (e.g., /pre -> /preset)
    - Preset IDs after '/preset ' (e.g., /preset rl_ -> /preset rl_hot_pants)
    - EP-133 subcommands after '/ep133 ' (connect, upload, clear, etc.)
    - Bank letters after '/ep133 upload ' or '/ep133 clear ' (A, B, C, D)
    """

    # EP-133 subcommands
    EP133_SUBCOMMANDS = ["connect", "disconnect", "status", "set", "list", "upload", "clear"]
    EP133_BANKS = ["A", "B", "C", "D"]

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
            "ep133": self._complete_ep133,
        }

    async def get_suggestion(self, value: str) -> str | None:
        """Get a suggestion for the current input.

        Args:
            value: Current input text

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

    def _complete_ep133(self, arg_str: str) -> str | None:
        """Complete EP-133 subcommands and their arguments.

        Args:
            arg_str: Everything after '/ep133 '

        Returns:
            Full command suggestion, or None
        """
        parts = arg_str.split()

        if len(parts) == 0 or (len(parts) == 1 and " " not in arg_str):
            # Completing subcommand
            prefix = parts[0] if parts else ""
            matches = [s for s in self.EP133_SUBCOMMANDS if s.startswith(prefix.lower())]
            if matches:
                return f"/ep133 {matches[0]}"
            return None

        # Have subcommand, check if it needs bank argument
        subcmd = parts[0].lower()
        if subcmd in ("upload", "clear"):
            bank_prefix = parts[1] if len(parts) > 1 else ""
            matches = [b for b in self.EP133_BANKS if b.startswith(bank_prefix.upper())]
            if matches:
                return f"/ep133 {subcmd} {matches[0]}"

        return None

    def get_all_matches(self, value: str) -> list[str]:
        """Get all matching completions for the current input.

        Args:
            value: Current input text

        Returns:
            List of all matching completions, sorted alphabetically
        """
        if not value.startswith("/"):
            return []

        content = value[1:]
        parts = content.split(maxsplit=1)

        if len(parts) == 0:
            return []

        if " " not in value:
            # Command completion
            prefix = parts[0]
            if not prefix:
                return []
            commands = list(TOOL_SCHEMAS.keys()) + list(TOOL_ALIASES.keys())
            return sorted(["/" + c for c in commands if c.startswith(prefix)])

        # Argument completion
        cmd = parts[0]
        arg_prefix = parts[1] if len(parts) == 2 else ""

        if cmd == "preset" and self.config:
            presets = [p[0] for p in self.config.get_preset_list()]
            return sorted([f"/preset {p}" for p in presets if p.startswith(arg_prefix)])
        elif cmd == "ep133":
            return self._get_ep133_matches(arg_prefix)

        return []

    def _get_ep133_matches(self, arg_str: str) -> list[str]:
        """Get all EP-133 completion matches.

        Args:
            arg_str: Everything after '/ep133 '

        Returns:
            List of matching completions
        """
        parts = arg_str.split()

        if len(parts) == 0 or (len(parts) == 1 and " " not in arg_str):
            # Completing subcommand
            prefix = parts[0] if parts else ""
            return [f"/ep133 {s}" for s in self.EP133_SUBCOMMANDS if s.startswith(prefix.lower())]

        # Have subcommand, check if it needs bank argument
        subcmd = parts[0].lower()
        if subcmd in ("upload", "clear"):
            bank_prefix = parts[1] if len(parts) > 1 else ""
            return [f"/ep133 {subcmd} {b}" for b in self.EP133_BANKS if b.startswith(bank_prefix.upper())]

        return []
