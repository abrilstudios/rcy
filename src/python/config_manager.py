import json
import os
import pathlib
import sys
from PyQt6.QtGui import QColor, QFont

class ConfigManager:
    """Manages application configuration, including colors, fonts, and strings"""
    
    def __init__(self):
        self.colors = {}
        self.fonts = {}
        self.strings = {}
        self.ui = {}
        self.presets = {}
        self.load_config()
    
    def load_config(self):
        """Load configuration from files"""
        try:
            # Get the path to the config directory
            current_file = pathlib.Path(__file__)
            project_root = current_file.parent.parent.parent
            config_dir = os.path.join(project_root, "config")
            presets_dir = os.path.join(project_root, "presets")
            
            colors_path = os.path.join(config_dir, "colors.json")
            strings_path = os.path.join(config_dir, "strings.json")
            ui_path = os.path.join(config_dir, "ui.json")
            presets_path = os.path.join(presets_dir, "presets.json")
            
            # Load colors from JSON file
            if os.path.exists(colors_path):
                with open(colors_path, 'r') as f:
                    config = json.load(f)
                    self.colors = config.get('palette', {})
                    self.fonts = config.get('fonts', {})
                print(f"Loaded color palette from {colors_path}")
            else:
                print(f"Colors config file not found: {colors_path}, using defaults")
                self._set_color_defaults()
                
            # Load strings from JSON file
            if os.path.exists(strings_path):
                with open(strings_path, 'r') as f:
                    self.strings = json.load(f)
                print(f"Loaded string resources from {strings_path}")
            else:
                print(f"Strings config file not found: {strings_path}, using defaults")
                self._set_string_defaults()
                
            # Load UI configuration from JSON file
            if os.path.exists(ui_path):
                with open(ui_path, 'r') as f:
                    self.ui = json.load(f)
                print(f"Loaded UI configuration from {ui_path}")
            else:
                print(f"UI config file not found: {ui_path}, using defaults")
                self._set_ui_defaults()
                
            # Load presets from JSON file
            if os.path.exists(presets_path):
                with open(presets_path, 'r') as f:
                    self.presets = json.load(f)
                print(f"Loaded preset catalog from {presets_path}")
            else:
                print(f"ERROR: Presets file not found: {presets_path}")
                sys.exit(1)  # Exit with error code
        except Exception as e:
            print(f"Error loading config: {e}")
            self._set_color_defaults()
            self._set_string_defaults()
            self._set_ui_defaults()
    
    def _set_color_defaults(self):
        """Set default colors and fonts if config can't be loaded"""
        self.colors = {
            "background": "#cbe9f3",
            "waveform": "#0a2239",
            "startMarker": "#007fa3",
            "endMarker": "#007fa3",
            "sliceActive": "#7f8fa6",
            "sliceHover": "#a6b5bd",
            "gridLines": "#7f8fa6",
            "selectionHighlight": "#ff3366",
            "cutButton": "#000000"
        }
        self.fonts = {
            "primary": "Futura PT Book"
        }
        
    def _set_string_defaults(self):
        """Set default strings if config can't be loaded"""
        self.strings = {
            "ui": {
                "windowTitle": "Recycle View",
                "applicationName": "RCY",
                "organizationName": "Abril Audio Labs",
                "organizationDomain": "abrilaudio.com"
            },
            "menus": {
                "file": "File",
                "help": "Help",
                "open": "Open",
                "export": "Export", 
                "saveAs": "Save As",
                "keyboardShortcuts": "Keyboard Shortcuts",
                "about": "About"
            },
            "buttons": {
                "zoomIn": "Zoom In",
                "zoomOut": "Zoom Out",
                "cut": "Cut Selection",
                "splitBars": "Split by Bars",
                "splitTransients": "Split by Transients",
                "close": "Close"
            },
            "labels": {
                "numBars": "Number of bars:",
                "tempo": "Tempo:",
                "onsetThreshold": "Onset Threshold:",
                "barResolutions": ["4th notes", "8th notes", "16th notes"]
            }
        }
    
    def _set_ui_defaults(self):
        """Set default UI configuration if ui.json can't be loaded"""
        self.ui = {
            "markerHandles": {
                "width": 16,
                "height": 10,
                "offsetY": 0
            }
        }
    
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

# Create a singleton instance
config = ConfigManager()