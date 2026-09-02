"""Context-aware tab completion for slash commands."""

import os
from pathlib import Path

from textual.suggester import Suggester

from tui.agents.tools import TOOL_SCHEMAS, TOOL_ALIASES


class CommandSuggester(Suggester):
    """Suggester that provides context-aware completions for slash commands.

    Provides completions for:
    - Command names after '/' (e.g., /pre -> /preset)
    - Preset IDs after '/preset ' (e.g., /preset rl_ -> /preset rl_hot_pants)
    - File paths after '/import ' (directories and .wav files)
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
            "import": self._complete_import,
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

    def _complete_import(self, prefix: str) -> str | None:
        """Complete a file path for import.

        Args:
            prefix: Partial file path

        Returns:
            Full command with path suggestion, or None
        """
        matches = self._get_path_matches(prefix)
        if matches:
            return f"/import {matches[0]}"
        return None

    def _get_path_matches(self, prefix: str) -> list[str]:
        """Get matching directories and WAV files for a path prefix.

        Args:
            prefix: Partial file path (can be empty, relative, or absolute)

        Returns:
            Sorted list of matching paths (directories end with /)
        """
        if not prefix:
            # Empty prefix: list current directory
            base_dir = Path.cwd()
            name_prefix = ""
        else:
            path = Path(prefix).expanduser()
            if prefix.endswith("/") or prefix.endswith(os.sep):
                # Ends with separator: list contents of that directory
                base_dir = path
                name_prefix = ""
            else:
                # Partial name: list parent directory, filter by prefix
                base_dir = path.parent
                name_prefix = path.name

        if not base_dir.is_dir():
            return []

        matches = []
        try:
            for entry in base_dir.iterdir():
                name = entry.name
                # Skip hidden files
                if name.startswith("."):
                    continue
                # Filter by prefix if provided
                if name_prefix and not name.lower().startswith(name_prefix.lower()):
                    continue
                # Include directories (with trailing /) and .wav files
                if entry.is_dir():
                    matches.append(str(entry) + "/")
                elif entry.suffix.lower() == ".wav":
                    matches.append(str(entry))
        except PermissionError:
            return []

        return sorted(matches)

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
        elif cmd == "import":
            return [f"/import {p}" for p in self._get_path_matches(arg_prefix)]

        return []
