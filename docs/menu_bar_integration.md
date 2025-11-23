# MenuBarManager Integration Guide

## Overview

The `MenuBarManager` class extracts all menu bar creation and management logic from `rcy_view.py` into a separate, reusable component located at `src/python/ui/menu_bar.py`.

## Class Structure

**File:** `/Users/palaitis/Development/rcy/src/python/ui/menu_bar.py`
**Lines of Code:** 223 lines

### Public API

The `MenuBarManager` class provides the following public methods:

#### Constructor

```python
def __init__(
    self,
    parent: Any,
    controller: Any,
    on_open_session: Callable[[], None],
    on_import_audio: Callable[[], None],
    on_preset_selected: Callable[[str], None],
    on_export: Callable[[], None],
    on_save_as: Callable[[], None],
    on_toggle_playback_tempo: Callable[[bool], None],
    on_playback_mode_changed: Callable[[str], None],
    on_show_shortcuts: Callable[[], None],
    on_show_about: Callable[[], None]
) -> None
```

All user interactions with the menu are communicated back to the parent window via callback functions.

#### Main Methods

1. **`create_menu_bar() -> QMenuBar`**
   - Creates and returns a fully configured menu bar
   - This is the main entry point for creating the menu

2. **`update_playback_tempo_action(enabled: bool) -> None`**
   - Updates the playback tempo menu action state
   - Used when playback tempo is toggled from UI controls

3. **`update_playback_mode_menu(mode: str) -> None`**
   - Updates the playback mode menu to reflect current mode
   - Accepts: "one-shot", "loop", or "loop-reverse"

### Private Methods

- `_create_file_menu()` - Creates File menu with all file operations
- `_create_options_menu()` - Creates Options menu with playback settings
- `_create_help_menu()` - Creates Help menu with documentation
- `_populate_presets_menu(menu: QMenu)` - Populates preset submenu

## Signal/Callback Pattern

The `MenuBarManager` uses a **callback pattern** rather than Qt signals. This design choice:

1. **Simplifies integration** - No need to define new signals
2. **Reduces coupling** - The manager doesn't need to know about RcyView's signal structure
3. **Improves testability** - Easy to mock callbacks for testing
4. **Maintains flexibility** - Parent window can easily transform callbacks to signals if needed

### Callback Flow

```
User clicks menu item
    → QAction.triggered signal fires
    → MenuBarManager calls callback function
    → Parent window (RcyView) handles the action
```

## Integration with RcyView

### Current State (Before Integration)

In `rcy_view.py`, the menu bar is created directly in the `create_menu_bar()` method (lines 208-300), which is called during initialization (line 48).

### Future Integration (After Refactoring)

```python
# In rcy_view.py __init__:
from ui.menu_bar import MenuBarManager

class RcyView(QMainWindow):
    def __init__(self, controller: Any) -> None:
        super().__init__()
        self.controller = controller

        # ... other initialization ...

        self.init_ui()
        self._setup_menu_bar()

        # ... rest of initialization ...

    def _setup_menu_bar(self) -> None:
        """Create and configure the menu bar using MenuBarManager"""
        self.menu_manager = MenuBarManager(
            parent=self,
            controller=self.controller,
            on_open_session=self.load_session_file,
            on_import_audio=self.import_audio_file,
            on_preset_selected=self.load_preset,
            on_export=self.export_segments,
            on_save_as=self.save_as,
            on_toggle_playback_tempo=self.toggle_playback_tempo,
            on_playback_mode_changed=self.set_playback_mode,
            on_show_shortcuts=self.show_keyboard_shortcuts,
            on_show_about=self.show_about_dialog
        )

        # Create and set the menu bar
        menu_bar = self.menu_manager.create_menu_bar()
        self.setMenuBar(menu_bar)
```

### Methods That Need to Be Accessible

The following methods in `RcyView` must remain accessible as they are used as callbacks:

- `load_session_file()` - Line 1205
- `import_audio_file()` - Line 1214
- `load_preset(preset_id: str)` - Line 1153
- `export_segments()` - Line 349
- `save_as()` - Line 363
- `toggle_playback_tempo(enabled: bool)` - Line 76
- `set_playback_mode(mode: str)` - Line 1179
- `show_keyboard_shortcuts()` - Line 1252
- `show_about_dialog()` - Line 1319

### Updating Menu State from RcyView

When `RcyView` needs to update menu state (e.g., when controller changes playback mode):

```python
# In update_playback_mode_menu (line 1163):
def update_playback_mode_menu(self, mode: str) -> None:
    """Update the playback mode menu to reflect the current mode"""
    self.menu_manager.update_playback_mode_menu(mode)

# In toggle_playback_tempo (line 76):
def toggle_playback_tempo(self, enabled: bool) -> None:
    """Toggle playback tempo adjustment on/off"""
    # ... existing logic ...

    # Update menu action via manager
    self.menu_manager.update_playback_tempo_action(enabled)
```

## Benefits of This Design

1. **Separation of Concerns** - Menu bar logic is isolated from view logic
2. **Reusability** - MenuBarManager can be used in other PyQt6 applications
3. **Testability** - Menu bar can be tested independently
4. **Maintainability** - Changes to menu structure only affect one file
5. **Type Safety** - All callbacks have type hints for better IDE support
6. **Configurability** - Menus still read from config.json for i18n support

## Files Affected

- **New File:** `/Users/palaitis/Development/rcy/src/python/ui/menu_bar.py`
- **To Be Modified:** `/Users/palaitis/Development/rcy/src/python/rcy_view.py`
  - Remove `create_menu_bar()` method (lines 208-300)
  - Remove `populate_presets_menu()` method (lines 1141-1151)
  - Remove playback mode menu logic (embedded in create_menu_bar)
  - Add `_setup_menu_bar()` method
  - Update references to menu actions

## Next Steps

1. Test the MenuBarManager independently
2. Integrate into RcyView
3. Remove old menu bar code from RcyView
4. Update any references to `self.playback_tempo_action`, `self.one_shot_action`, etc.
   to access through `self.menu_manager.playback_tempo_action`
5. Run application tests to verify functionality
