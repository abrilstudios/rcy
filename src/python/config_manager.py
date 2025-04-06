import json
import os
import pathlib
from PyQt6.QtGui import QColor, QFont

class ConfigManager:
    """Manages application configuration, including colors and fonts"""
    
    def __init__(self):
        self.colors = {}
        self.fonts = {}
        self.load_config()
    
    def load_config(self):
        """Load configuration from files"""
        try:
            # Get the path to the config directory
            current_file = pathlib.Path(__file__)
            project_root = current_file.parent.parent.parent
            colors_path = os.path.join(project_root, "config", "colors.json")
            
            # Load colors from JSON file
            if os.path.exists(colors_path):
                with open(colors_path, 'r') as f:
                    config = json.load(f)
                    self.colors = config.get('palette', {})
                    self.fonts = config.get('fonts', {})
                print(f"Loaded color palette from {colors_path}")
            else:
                print(f"Config file not found: {colors_path}, using defaults")
                self._set_defaults()
        except Exception as e:
            print(f"Error loading config: {e}")
            self._set_defaults()
    
    def _set_defaults(self):
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

# Create a singleton instance
config = ConfigManager()