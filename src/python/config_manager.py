import json
import os
import pathlib
import sys
from PyQt6.QtGui import QColor, QFont
from typing import Union, Optional, Dict, Any

class ConfigManager:
    """Manages application configuration, including colors, fonts, and strings"""
    
    def __init__(self, cfg_path: Optional[Union[str, pathlib.Path]] = None, 
                 presets_path: Optional[Union[str, pathlib.Path]] = None,
                 exit_on_error: bool = True):
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
        self.presets = {}
        self.exit_on_error = exit_on_error
        self._cfg: Dict[str, Any] = {}
        
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
        """Get the default path to the presets.json file."""
        base = pathlib.Path(__file__).parent.parent.parent
        return base / "presets" / "presets.json"
        
    def load_config(self):
        """Load master configuration from the configured paths."""
        # Load master config
        try:
            with open(self.cfg_path, 'r') as f:
                self._cfg = json.load(f)
        except Exception as e:
            error_msg = f"Critical error loading configuration '{self.cfg_path}': {e}"
            print(error_msg, file=sys.stderr)
            if self.exit_on_error:
                sys.exit(1)
            else:
                raise RuntimeError(error_msg)
        
        # Validate and assign sections
        try:
            c = self._cfg["colors"]
            self.colors = c["palette"]
            self.fonts = c["fonts"]
            self.strings = self._cfg["strings"]
            self.ui = self._cfg["ui"]
            self.audio = self._cfg["audio"]
        except KeyError as e:
            error_msg = f"Configuration missing key: {e}"
            print(error_msg, file=sys.stderr)
            if self.exit_on_error:
                sys.exit(1)
            else:
                raise KeyError(error_msg)
        
        # Load presets
        try:
            with open(self.presets_path, 'r') as f:
                self.presets = json.load(f)
        except Exception as e:
            error_msg = f"Critical error loading presets '{self.presets_path}': {e}"
            print(error_msg, file=sys.stderr)
            if self.exit_on_error:
                sys.exit(1)
            else:
                raise RuntimeError(error_msg)
    
    # Default-setting methods removed: loading now always requires valid config.json
    
    def get_color(self, key, default=None):
        """Get a color from the palette by key"""
        color_hex = self.colors.get(key, default)
        if color_hex:
            return QColor(color_hex)
        return QColor("#000000")  # Fallback to black
    
    def get_qt_color(self, key, default=None):
        """Get a color as a string for stylesheet use"""
        return self.colors.get(key, default or "#000000")
    
    def get_font(self, key="primary"):
        """Get a font by key, with system fallbacks"""
        font_name = self.fonts.get(key, "Arial")
        font = QFont(font_name)
        
        # Add fallbacks if Futura PT Book isn't available
        if key == "primary":
            # Try common geometric sans-serifs as fallbacks
            fallbacks = ["Futura", "Century Gothic", "Avant Garde", "Avenir", "Gill Sans", "Arial"]
            for fallback in fallbacks:
                if fallback != font_name:  # Don't add the same font twice
                    font.insertSubstitution(font_name, fallback)
        
        return font
    
    def get_string(self, category, key, default=None):
        """Get a string resource by category and key"""
        if category in self.strings and key in self.strings[category]:
            return self.strings[category][key]
        return default or key
    
    def get_nested_string(self, path, default=None):
        """Get a string resource by dot-notation path (e.g., 'ui.windowTitle')"""
        parts = path.split('.')
        current = self.strings
        
        for part in parts:
            if part in current:
                current = current[part]
            else:
                return default or path
        
        return current if isinstance(current, (str, list)) else default or path
        
    def get_ui_setting(self, category, key, default=None):
        """Get a UI setting value by category and key"""
        if category in self.ui and key in self.ui[category]:
            return self.ui[category][key]
        return default
        
    def get_preset_info(self, preset_id):
        """Get information about a specific preset by its ID"""
        return self.presets.get(preset_id)
        
    def get_preset_list(self):
        """Get a list of available presets with their names"""
        preset_list = []
        for preset_id, preset_data in self.presets.items():
            name = preset_data.get('name', preset_id)
            preset_list.append((preset_id, name))
        return preset_list
    
    def get_setting(self, section: str, key: str, default=None):  # noqa: C901
        """Get a generic setting from the master config"""
        try:
            return self._cfg.get(section, {}).get(key, default)
        except Exception:
            return default
        

# Create a singleton instance
config = ConfigManager()