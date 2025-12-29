"""Skin manager for TUI theming.

Loads and manages color skins for the TUI display.
Skins are JSON files in config/skins/ directory.
"""

import json
import logging
import pathlib
from typing import Optional

logger = logging.getLogger(__name__)


# Default skin colors (fallback if no skin file loaded)
DEFAULT_COLORS = {
    "waveform": {
        "background": "",
        "foreground": "white",
        "peak": "bright_white"
    },
    "markers": {
        "L": "cyan",
        "R": "cyan",
        "segment": "yellow",
        "focused": "bright_green"
    },
    "border": {
        "normal": "dim white",
        "focused": "cyan"
    },
    "command_input": {
        "background": "",
        "foreground": "white",
        "prompt": "cyan"
    },
    "output": {
        "background": "",
        "foreground": "white",
        "error": "red",
        "success": "green",
        "info": "cyan"
    },
    "header": {
        "filename": "bright_white",
        "bpm": "yellow",
        "info": "dim white"
    },
    "segments": {
        "number": "yellow",
        "active": "bright_green"
    },
    "time_axis": {
        "foreground": "dim white"
    }
}


class SkinManager:
    """Manages loading and switching of TUI skins."""

    _instance: Optional['SkinManager'] = None

    def __init__(self, skins_dir: Optional[pathlib.Path] = None):
        """Initialize SkinManager.

        Args:
            skins_dir: Path to skins directory. Defaults to config/skins/
        """
        if skins_dir is None:
            base = pathlib.Path(__file__).parent.parent.parent.parent
            skins_dir = base / "config" / "skins"

        self.skins_dir = skins_dir
        self.current_skin_name = "default"
        self.colors = DEFAULT_COLORS.copy()
        self._available_skins: dict[str, dict] = {}

        # Load available skins
        self._load_available_skins()

    @classmethod
    def get_instance(cls, skins_dir: Optional[pathlib.Path] = None) -> 'SkinManager':
        """Get singleton instance of SkinManager."""
        if cls._instance is None:
            cls._instance = cls(skins_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    def _load_available_skins(self) -> None:
        """Scan skins directory and load all available skins."""
        if not self.skins_dir.exists():
            logger.warning("Skins directory not found: %s", self.skins_dir)
            return

        for skin_file in self.skins_dir.glob("*.json"):
            try:
                with open(skin_file, 'r') as f:
                    skin_data = json.load(f)
                    skin_name = skin_data.get("name", skin_file.stem)
                    self._available_skins[skin_name] = skin_data
                    logger.debug("Loaded skin: %s", skin_name)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load skin %s: %s", skin_file, e)

    def list_skins(self) -> list[str]:
        """Return list of available skin names."""
        return sorted(self._available_skins.keys())

    def get_skin_info(self, name: str) -> Optional[dict]:
        """Get skin metadata.

        Args:
            name: Skin name

        Returns:
            Dict with name and description, or None if not found
        """
        if name in self._available_skins:
            skin = self._available_skins[name]
            return {
                "name": skin.get("name", name),
                "description": skin.get("description", "No description")
            }
        return None

    def load_skin(self, name: str) -> bool:
        """Load a skin by name.

        Args:
            name: Name of skin to load

        Returns:
            True if skin loaded successfully, False otherwise
        """
        if name not in self._available_skins:
            logger.warning("Skin not found: %s", name)
            return False

        skin_data = self._available_skins[name]
        skin_colors = skin_data.get("colors", {})

        # Deep merge with defaults
        self.colors = self._deep_merge(DEFAULT_COLORS, skin_colors)
        self.current_skin_name = name

        logger.info("Loaded skin: %s", name)
        return True

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_color(self, *path: str) -> str:
        """Get a color value by path.

        Args:
            *path: Path to color value (e.g., "markers", "L")

        Returns:
            Color string (Rich color name) or empty string
        """
        current = self.colors
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return ""
        return current if isinstance(current, str) else ""

    def get_current_skin(self) -> str:
        """Get name of currently loaded skin."""
        return self.current_skin_name


# Module-level convenience function
def get_skin_manager() -> SkinManager:
    """Get the singleton SkinManager instance."""
    return SkinManager.get_instance()
