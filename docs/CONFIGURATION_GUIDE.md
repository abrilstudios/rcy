# RCY Configuration Guide

## Overview

The RCY application uses a centralized configuration system managed through the `ConfigManager` class in `src/python/config_manager.py`. Configuration is stored in JSON format and accessed via a singleton instance.

## Configuration File Structure

Configuration files are located in:
- **Main Config**: `config/config.json`
- **Presets**: `presets/presets.json`

The main configuration file is structured into these sections:

### 1. Colors (`colors`)

Contains color palette definitions and font specifications.

```json
{
  "colors": {
    "palette": {
      "background": "#cbe9f3",
      "textColor": "#0a2239",
      "waveform": "#0a2239",
      "startMarker": "#007fa3",
      "endMarker": "#007fa3",
      "sliceActive": "#7f8fa6",
      "sliceHover": "#a6b5bd",
      "gridLines": "#7f8fa6",
      "selectionHighlight": "#ff3366",
      "activeSegmentHighlight": "#cccccc",
      "cutButton": "#000000"
    },
    "fonts": {
      "primary": "Futura PT Book"
    }
  }
}
```

**Access Pattern**: Use `config.get_color()` or `config.get_qt_color()`

### 2. Strings (`strings`)

Contains all user-facing text strings organized by category.

Categories:
- `ui`: Application window titles and names
- `menus`: Menu item labels
- `buttons`: Button labels
- `labels`: Form labels and descriptions
- `dialogs`: Dialog titles and messages
- `shortcuts`: Keyboard shortcut descriptions
- `about`: About dialog content

**Access Pattern**: Use `config.get_string(category, key)`

Example:
```python
title = config.get_string("ui", "windowTitle")  # Returns "RCY"
button = config.get_string("buttons", "cut")     # Returns "Cut Selection"
```

### 3. UI Configuration (`ui`)

Contains UI-specific settings like marker dimensions and snapping behavior.

```json
{
  "ui": {
    "markerHandles": {
      "type": "rectangle",
      "width": 8,
      "height": 14,
      "offsetY": 0
    },
    "markerSnapping": {
      "snapThreshold": 0.05
    }
  }
}
```

**Access Pattern**: Use `config.get_ui_setting(category, key, default)`

Example:
```python
width = config.get_ui_setting("markerHandles", "width", 16)
snap = config.get_ui_setting("markerSnapping", "snapThreshold", 0.025)
```

### 4. Audio Configuration (`audio`)

Contains audio processing settings including downsampling, transient detection, playback, and effects.

```json
{
  "audio": {
    "stereoDisplay": true,
    "downsampling": {
      "enabled": true,
      "method": "envelope",
      "alwaysApply": true,
      "targetLength": 2000,
      "minLength": 1000,
      "maxLength": 5000
    },
    "transientDetection": {
      "threshold": 0.2,
      "waitTime": 1,
      "preMax": 1,
      "postMax": 1,
      "deltaFactor": 0.1
    },
    "playback": {
      "mode": "one-shot"
    },
    "playbackTempo": {
      "enabled": false,
      "targetBpm": 120
    },
    "tailFade": {
      "enabled": false,
      "durationMs": 10,
      "curve": "exponential"
    }
  }
}
```

**Access Patterns**:
- For nested audio settings: Use `config.get_setting("audio", key, default)`
- For single boolean: Use `config.get_setting("audio", "stereoDisplay", default)`

Example:
```python
ds_config = config.get_setting("audio", "downsampling", {})
stereo = config.get_setting("audio", "stereoDisplay", True)
td_config = config.get_setting("audio", "transientDetection", {})
```

### 5. Logging Configuration (`logging`)

Contains application logging settings.

```json
{
  "logging": {
    "level": "INFO",
    "file": "logs/rcy.log",
    "maxBytes": 10485760,
    "backupCount": 3,
    "console": true
  }
}
```

**Access Pattern**: Use `config.get_logging_setting(key, default)`

Example:
```python
level = config.get_logging_setting("level", "INFO")
log_file = config.get_logging_setting("file", "logs/rcy.log")
```

## Configuration Access Methods

The `ConfigManager` class provides these methods for accessing configuration:

### Colors

```python
config.get_color(key, default=None) -> QColor
```
Returns a PyQt6 QColor object. Used for color values that need to be QColor instances.

```python
config.get_qt_color(key, default=None) -> str
```
Returns a color as a hex string. Used for stylesheet applications.

### Fonts

```python
config.get_font(key="primary") -> QFont
```
Returns a PyQt6 QFont object with system fallbacks.

### Strings

```python
config.get_string(category, key, default=None) -> str
```
Returns a user-facing string by category and key.

### UI Settings

```python
config.get_ui_setting(category, key, default=None) -> Any
```
Returns a UI configuration value from the `ui` section.

### Audio Settings

```python
config.get_setting(section, key, default=None) -> Any
```
Generic method to get any setting from the main configuration.

### Logging Settings

```python
config.get_logging_setting(key, default=None) -> Any
```
Returns a logging configuration value.

### Presets

```python
config.get_preset_info(preset_id) -> PresetInfo | None
```
Returns information about a specific preset.

```python
config.get_preset_list() -> list[tuple[str, str]]
```
Returns a list of available presets with their names.

## Unified Configuration Patterns

### Pattern: Color Access

All color access should use the unified pattern:

**For QColor objects:**
```python
color = config.get_color('colorKey')
# Usage: widget.setColor(color)
```

**For stylesheets:**
```python
style = f"background-color: {config.get_qt_color('background')};"
# Usage: widget.setStyleSheet(style)
```

### Pattern: String Access

Strings are organized by category. Always include the category:

```python
text = config.get_string("category", "key")
```

Categories: `ui`, `menus`, `buttons`, `labels`, `dialogs`, `shortcuts`, `about`

### Pattern: UI Settings

UI-specific dimensions and thresholds use the nested pattern:

```python
value = config.get_ui_setting("category", "key", default_value)
```

Examples:
- `config.get_ui_setting("markerHandles", "width", 16)`
- `config.get_ui_setting("markerSnapping", "snapThreshold", 0.025)`

### Pattern: Audio Configuration

Audio settings use the generic setting getter, typically retrieving entire subsections:

```python
audio_subsection = config.get_setting("audio", "subsectionKey", {})
```

For direct access to top-level audio keys:
```python
stereo_mode = config.get_setting("audio", "stereoDisplay", True)
```

### Pattern: Logging Settings

Logging settings use the specialized logging getter:

```python
log_level = config.get_logging_setting("level", "INFO")
```

## Files Using Configuration

### Core Configuration Management
- `src/python/config_manager.py` - Configuration manager implementation

### Main Application
- `src/python/main.py` - Application setup (strings, presets)
- `src/python/rcy_view.py` - Main window (UI settings, colors, strings)

### Controllers
- `src/python/controllers/application_controller.py` - Audio settings
- `src/python/controllers/audio_controller.py` - Presets
- `src/python/controllers/view_controller.py` - Downsampling config

### Audio Processing
- `src/python/audio_processor.py` - Audio config (transient detection, playback tempo)
- `src/python/high_performance_audio.py` - Tail fade config
- `src/python/export_utils.py` - Export settings
- `src/python/logging_config.py` - Logging setup

### UI Components
- `src/python/ui/control_panel.py` - Labels, threshold config
- `src/python/ui/dialogs.py` - Dialog strings, colors
- `src/python/ui/menu_bar.py` - Menu strings
- `src/python/ui/transport_controls.py` - Button strings, colors
- `src/python/ui/waveform/base.py` - UI settings (marker snapping, stereo display)
- `src/python/ui/waveform/marker_handles.py` - Marker colors, dimensions
- `src/python/ui/waveform/pyqtgraph_widget.py` - Colors
- `src/python/ui/waveform/segment_visualization.py` - Colors

## Configuration Best Practices

1. **Always Use Defaults**: Provide sensible defaults in config.get_*() calls
2. **Consistent Access Patterns**: Use the appropriate getter for each type (get_color, get_string, get_ui_setting, etc.)
3. **Avoid Direct Dictionary Access**: Never access `config.colors`, `config.strings`, etc. directly
4. **Group Related Settings**: Keep related configuration values in the same section
5. **Document New Keys**: When adding new config keys, update this guide
6. **Single Responsibility**: Each config section should have a clear, single purpose

## Adding New Configuration

To add new configuration:

1. **Update config.json** with the new setting in the appropriate section
2. **Add default handling** in the config.get_*() calls throughout the code
3. **Update this guide** with the new key location and access pattern
4. **Add to test fixtures** in tests/conftest.py if needed

## Initialization and Singleton Usage

The ConfigManager is initialized as a singleton instance at module load:

```python
from config_manager import config
# Access the singleton instance directly
```

The singleton is created with optional custom paths for testing:

```python
# For custom configuration locations (typically in tests)
from config_manager import ConfigManager
config_instance = ConfigManager(
    cfg_path="path/to/config.json",
    presets_path="path/to/presets.json",
    exit_on_error=False  # For testing
)
```

## Error Handling

Configuration errors are handled gracefully:
- Missing configuration files cause application exit (unless `exit_on_error=False`)
- Missing configuration keys are handled with defaults
- Invalid configuration values fall back to sensible defaults
- All errors are logged for debugging

## Testing

Configuration is mocked in tests using the `ConfigManager` class directly with custom paths or `exit_on_error=False`.
