import json
import os
import pathlib
import sys
import logging
from typing import Any

from custom_types import PresetInfo

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration, including colors, fonts, and strings"""

    colors: dict[str, str]
    fonts: dict[str, str]
    strings: dict[str, Any]
    ui: dict[str, Any]
    audio: dict[str, Any]
    presets: dict[str, Any]
    exit_on_error: bool
    _cfg: dict[str, Any]
    cfg_path: str | pathlib.Path
    presets_path: str | pathlib.Path

    def __init__(
        self,
        cfg_path: str | pathlib.Path | None = None,
        presets_path: str | pathlib.Path | None = None,
        exit_on_error: bool = True
    ) -> None:
        """Initialize the ConfigManager with optional custom paths.

        Args:
            cfg_path: Path to the config.json file (defaults to standard location if None)
            presets_path: Path to the presets.json file (defaults to standard location if None)
            exit_on_error: Whether to exit the program on configuration errors
        """
        self.colors = {}
        self.fonts = {}
        self.strings = {}
        self.ui = {}
        self.audio = {}
        self.presets = {}
        self.exit_on_error = exit_on_error
        self._cfg = {}

        # Store paths for configuration files
        self.cfg_path = cfg_path if cfg_path is not None else self._default_config_path()
        self.presets_path = presets_path if presets_path is not None else self._default_presets_path()

        # Load configuration
        self.load_config()

    def _default_config_path(self) -> pathlib.Path:
        """Get the default path to the config.json file."""
        base = pathlib.Path(__file__).parent.parent.parent
        return base / "config" / "config.json"

    def _default_presets_path(self) -> pathlib.Path:
        """Get the default path to the presets directory.

        Presets are now loaded from config/presets/*.json files which are
        merged at load time. This allows modular preset management where
        each sample pack can have its own JSON file.
        """
        base = pathlib.Path(__file__).parent.parent.parent
        return base / "config" / "presets"

    def load_config(self) -> None:
        """Load master configuration from the configured paths."""
        # Load master config
        try:
            with open(self.cfg_path, 'r') as f:
                self._cfg = json.load(f)
        except Exception as e:
            error_msg = f"Critical error loading configuration '%s': %s"
            logger.error(error_msg, self.cfg_path, e)
            if self.exit_on_error:
                sys.exit(1)
            else:
                raise RuntimeError(f"Critical error loading configuration '{self.cfg_path}': {e}")
        
        # Validate and assign sections
        try:
            c = self._cfg["colors"]
            self.colors = c["palette"]
            self.fonts = c["fonts"]
            self.strings = self._cfg["strings"]
            self.ui = self._cfg["ui"]
            self.audio = self._cfg["audio"]
        except KeyError as e:
            error_msg = "Configuration missing key: %s"
            logger.error(error_msg, e)
            if self.exit_on_error:
                sys.exit(1)
            else:
                raise KeyError(f"Configuration missing key: {e}")
        
        # Load presets from config/presets/*.json (merged)
        self._load_presets()

    def _load_presets(self) -> None:
        """Load and merge all preset files from the presets directory.

        Presets are loaded from config/presets/*.json files. Each file contains
        a flat dict of preset_id -> preset_data. Files are loaded in sorted order
        and merged, with collision detection to prevent duplicate preset IDs.

        For backwards compatibility, if presets_path is a file (not directory),
        it will be loaded directly as a single JSON file.
        """
        presets_path = pathlib.Path(self.presets_path)

        # Backwards compatibility: if path is a file, load it directly
        if presets_path.is_file():
            try:
                with open(presets_path, 'r') as f:
                    self.presets = json.load(f)
                return
            except Exception as e:
                error_msg = "Critical error loading presets '%s': %s"
                logger.error(error_msg, presets_path, e)
                if self.exit_on_error:
                    sys.exit(1)
                else:
                    raise RuntimeError(f"Critical error loading presets '{presets_path}': {e}")

        # Load from directory: merge all *.json files
        if not presets_path.is_dir():
            error_msg = f"Presets path is not a file or directory: {presets_path}"
            logger.error(error_msg)
            if self.exit_on_error:
                sys.exit(1)
            else:
                raise RuntimeError(error_msg)

        self.presets = {}
        json_files = sorted(presets_path.glob("*.json"))

        if not json_files:
            logger.warning("No preset files found in %s", presets_path)
            return

        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    file_presets = json.load(f)

                # Check for ID collisions
                for preset_id in file_presets:
                    if preset_id in self.presets:
                        error_msg = f"Duplicate preset ID '{preset_id}' in {json_file.name}"
                        logger.error(error_msg)
                        if self.exit_on_error:
                            sys.exit(1)
                        else:
                            raise ValueError(error_msg)

                self.presets.update(file_presets)
                logger.debug("Loaded %d presets from %s", len(file_presets), json_file.name)

            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in preset file {json_file}: {e}"
                logger.error(error_msg)
                if self.exit_on_error:
                    sys.exit(1)
                else:
                    raise RuntimeError(error_msg)

        logger.info("Loaded %d total presets from %d files", len(self.presets), len(json_files))

    # Default-setting methods removed: loading now always requires valid config.json

    def get_color(self, key: str, default: str | None = None) -> str:
        """Get a color hex string from the palette by key"""
        return self.colors.get(key, default or "#000000")

    def get_font(self, key: str = "primary") -> str:
        """Get a font name by key"""
        return self.fonts.get(key, "Arial")

    def get_string(self, category: str, key: str, default: str | None = None) -> str:
        """Get a string resource by category and key"""
        if category in self.strings and key in self.strings[category]:
            return self.strings[category][key]
        return default or key

    def get_nested_string(self, path: str, default: str | None = None) -> str | list[Any]:
        """Get a string resource by dot-notation path (e.g., 'ui.windowTitle')"""
        parts = path.split('.')
        current: Any = self.strings

        for part in parts:
            if part in current:
                current = current[part]
            else:
                return default or path

        return current if isinstance(current, (str, list)) else default or path

    def get_ui_setting(self, category: str, key: str, default: Any = None) -> Any:
        """Get a UI setting value by category and key"""
        if category in self.ui and key in self.ui[category]:
            return self.ui[category][key]
        return default

    def get_preset_info(self, preset_id: str) -> PresetInfo | None:
        """Get information about a specific preset by its ID"""
        return self.presets.get(preset_id)

    def get_preset_list(self) -> list[tuple[str, str]]:
        """Get a list of available presets with their names"""
        preset_list: list[tuple[str, str]] = []
        for preset_id, preset_data in self.presets.items():
            name = preset_data.get('name', preset_id)
            preset_list.append((preset_id, name))
        return preset_list

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Get a generic setting from the master config"""
        try:
            return self._cfg.get(section, {}).get(key, default)
        except Exception:
            return default

    def set_setting(self, section: str, key: str, value: Any) -> None:
        """Set a setting in memory (does not persist to file).

        Args:
            section: Configuration section (e.g., 'audio', 'ui')
            key: Setting key within the section
            value: Value to set
        """
        if section not in self._cfg:
            self._cfg[section] = {}
        self._cfg[section][key] = value

    def get_logging_setting(self, key: str, default: Any = None) -> Any:
        """Get a logging configuration setting"""
        try:
            return self._cfg.get("logging", {}).get(key, default)
        except Exception:
            return default

    # ============================================================================
    # Unified Audio Configuration Accessors
    # ============================================================================

    def get_stereo_display(self, default: bool = True) -> bool:
        """Get stereo display mode setting from audio configuration.

        Returns:
            bool: Whether stereo display is enabled (True for stereo, False for mono)
        """
        return self.get_setting("audio", "stereoDisplay", default)

    def get_downsampling_config(self) -> dict[str, Any]:
        """Get downsampling configuration from audio settings.

        Returns:
            dict: Downsampling configuration with keys:
                - enabled: Whether downsampling is enabled
                - method: 'envelope' or 'simple'
                - alwaysApply: Whether to always apply downsampling
                - targetLength: Target sample count
                - minLength: Minimum sample count
                - maxLength: Maximum sample count
        """
        return self.get_setting("audio", "downsampling", {})

    def get_transient_detection_config(self) -> dict[str, Any]:
        """Get transient detection configuration from audio settings.

        Returns:
            dict: Transient detection configuration with keys:
                - threshold: Detection threshold
                - waitTime: Wait time between detections
                - preMax: Pre-maximum window
                - postMax: Post-maximum window
                - deltaFactor: Delta factor for detection
        """
        return self.get_setting("audio", "transientDetection", {})

    def get_playback_tempo_config(self) -> dict[str, Any]:
        """Get playback tempo configuration from audio settings.

        Returns:
            dict: Playback tempo configuration with keys:
                - enabled: Whether tempo adjustment is enabled
                - targetBpm: Target BPM for tempo adjustment
        """
        return self.get_setting("audio", "playbackTempo", {})

    def get_tail_fade_config(self) -> dict[str, Any]:
        """Get tail fade configuration from audio settings.

        Returns:
            dict: Tail fade configuration with keys:
                - enabled: Whether tail fade is enabled
                - durationMs: Duration in milliseconds
                - curve: Fade curve type ('exponential', 'linear', etc.)
        """
        return self.get_setting("audio", "tailFade", {})

    def get_playback_config(self) -> dict[str, Any]:
        """Get playback configuration from audio settings.

        Returns:
            dict: Playback configuration with keys:
                - mode: Playback mode ('one-shot', 'loop', etc.)
        """
        return self.get_setting("audio", "playback", {})

    # ============================================================================
    # Unified UI Configuration Accessors
    # ============================================================================

    def get_marker_handle_config(self) -> dict[str, Any]:
        """Get marker handle configuration from UI settings.

        Returns:
            dict: Marker handle configuration with keys:
                - type: Handle type ('rectangle')
                - width: Handle width in pixels
                - height: Handle height in pixels
                - offsetY: Y offset in pixels
        """
        if "markerHandles" in self.ui:
            return self.ui["markerHandles"]
        return {"type": "rectangle", "width": 8, "height": 14, "offsetY": 0}

    def get_snap_threshold(self, default: float = 0.025) -> float:
        """Get marker snapping threshold from UI settings.

        Args:
            default: Default threshold in seconds

        Returns:
            float: Snap threshold in seconds
        """
        return self.get_ui_setting("markerSnapping", "snapThreshold", default)


# Create a singleton instance
config = ConfigManager()