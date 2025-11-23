"""Menu bar manager for RCY application.

This module provides the MenuBarManager class which handles creation and management
of the application's menu bar, including File, Options, and Help menus.
"""

from typing import Any, Callable
from PyQt6.QtWidgets import QMenuBar, QMenu
from PyQt6.QtGui import QAction, QActionGroup
from config_manager import config
from enums import PlaybackMode
import logging

logger = logging.getLogger(__name__)


class MenuBarManager:
    """Manages the creation and configuration of the application menu bar.

    The MenuBarManager creates a complete menu bar with:
    - File menu (Open Session, Import Audio, Open Preset, Export, Save As)
    - Options menu (Playback Tempo, Playback Mode)
    - Help menu (Keyboard Shortcuts, About)

    It uses callbacks to communicate user actions back to the main window.
    """

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
    ) -> None:
        """Initialize the MenuBarManager.

        Args:
            parent: The parent window (typically RcyView)
            controller: The application controller
            on_open_session: Callback for Open Session action
            on_import_audio: Callback for Import Audio action
            on_preset_selected: Callback for preset selection (takes preset_id: str)
            on_export: Callback for Export action
            on_save_as: Callback for Save As action
            on_toggle_playback_tempo: Callback for toggling playback tempo (takes enabled: bool)
            on_playback_mode_changed: Callback for playback mode changes (takes mode: str)
            on_show_shortcuts: Callback for showing keyboard shortcuts dialog
            on_show_about: Callback for showing about dialog
        """
        self.parent = parent
        self.controller = controller
        self.on_open_session = on_open_session
        self.on_import_audio = on_import_audio
        self.on_preset_selected = on_preset_selected
        self.on_export = on_export
        self.on_save_as = on_save_as
        self.on_toggle_playback_tempo = on_toggle_playback_tempo
        self.on_playback_mode_changed = on_playback_mode_changed
        self.on_show_shortcuts = on_show_shortcuts
        self.on_show_about = on_show_about

        # Menu bar and action references
        self.menu_bar: QMenuBar | None = None
        self.playback_tempo_action: QAction | None = None
        self.one_shot_action: QAction | None = None
        self.loop_action: QAction | None = None
        self.loop_reverse_action: QAction | None = None

    def create_menu_bar(self) -> QMenuBar:
        """Create and configure the complete menu bar.

        Returns:
            QMenuBar: The configured menu bar ready to be added to the main window
        """
        self.menu_bar = QMenuBar(self.parent)

        # Create the three main menus
        self._create_file_menu()
        self._create_options_menu()
        self._create_help_menu()

        return self.menu_bar

    def _create_file_menu(self) -> None:
        """Create the File menu with all file-related actions."""
        file_menu = self.menu_bar.addMenu(config.get_string("menus", "file"))

        # Open Session action
        open_action = QAction("Open Session", self.parent)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Open a saved session file')
        open_action.triggered.connect(self.on_open_session)
        file_menu.addAction(open_action)

        # Import Audio action
        import_action = QAction("Import Audio", self.parent)
        import_action.setShortcut('Ctrl+I')
        import_action.setStatusTip('Import a new audio file')
        import_action.triggered.connect(self.on_import_audio)
        file_menu.addAction(import_action)

        # Open Preset submenu
        presets_menu = file_menu.addMenu("Open Preset")
        self._populate_presets_menu(presets_menu)

        # Export action
        export_action = QAction(config.get_string("menus", "export"), self.parent)
        export_action.setShortcut('Ctrl+E')
        export_action.setStatusTip('Export segments and SFZ file')
        export_action.triggered.connect(self.on_export)
        file_menu.addAction(export_action)

        # Save As action
        save_as_action = QAction(config.get_string("menus", "saveAs"), self.parent)
        save_as_action.triggered.connect(self.on_save_as)
        file_menu.addAction(save_as_action)

    def _create_options_menu(self) -> None:
        """Create the Options menu with playback settings."""
        options_menu = self.menu_bar.addMenu("Options")

        # Playback Tempo submenu
        playback_tempo_menu = options_menu.addMenu("Playback Tempo")

        # Enable/disable playback tempo adjustment
        self.playback_tempo_action = QAction("Enable Tempo Adjustment", self.parent)
        self.playback_tempo_action.setCheckable(True)
        self.playback_tempo_action.triggered.connect(self.on_toggle_playback_tempo)
        playback_tempo_menu.addAction(self.playback_tempo_action)

        # Add separator
        playback_tempo_menu.addSeparator()

        # Playback Mode submenu
        playback_mode_menu = options_menu.addMenu("Playback Mode")

        # Create action group for radio button behavior
        playback_mode_group = QActionGroup(self.parent)
        playback_mode_group.setExclusive(True)

        # Add playback mode options with radio buttons
        self.one_shot_action = QAction("One-Shot", self.parent)
        self.one_shot_action.setCheckable(True)
        self.one_shot_action.triggered.connect(lambda: self.on_playback_mode_changed(PlaybackMode.ONE_SHOT.value))
        playback_mode_group.addAction(self.one_shot_action)
        playback_mode_menu.addAction(self.one_shot_action)

        self.loop_action = QAction("Loop", self.parent)
        self.loop_action.setCheckable(True)
        self.loop_action.triggered.connect(lambda: self.on_playback_mode_changed(PlaybackMode.LOOP.value))
        playback_mode_group.addAction(self.loop_action)
        playback_mode_menu.addAction(self.loop_action)

        self.loop_reverse_action = QAction("Loop and Reverse", self.parent)
        self.loop_reverse_action.setCheckable(True)
        self.loop_reverse_action.triggered.connect(lambda: self.on_playback_mode_changed(PlaybackMode.LOOP_REVERSE.value))
        playback_mode_group.addAction(self.loop_reverse_action)
        playback_mode_menu.addAction(self.loop_reverse_action)

        # Set initial selection to one-shot (default)
        # The controller will update this later if needed
        self.one_shot_action.setChecked(True)

    def _create_help_menu(self) -> None:
        """Create the Help menu with documentation and about actions."""
        help_menu = self.menu_bar.addMenu(config.get_string("menus", "help"))

        # Keyboard shortcuts action
        shortcuts_action = QAction(config.get_string("menus", "keyboardShortcuts"), self.parent)
        shortcuts_action.triggered.connect(self.on_show_shortcuts)
        help_menu.addAction(shortcuts_action)

        # About action
        about_action = QAction(config.get_string("menus", "about"), self.parent)
        about_action.triggered.connect(self.on_show_about)
        help_menu.addAction(about_action)

    def _populate_presets_menu(self, menu: QMenu) -> None:
        """Populate the presets menu with available presets.

        Args:
            menu: The QMenu to populate with preset actions
        """
        # Get available presets from controller
        presets = self.controller.get_available_presets()

        # Add each preset to the menu
        for preset_id, preset_name in presets:
            action = QAction(preset_name, self.parent)
            # Create a lambda with default arguments to avoid late binding issues
            action.triggered.connect(lambda checked=False, preset=preset_id: self.on_preset_selected(preset))
            menu.addAction(action)

    def update_playback_tempo_action(self, enabled: bool) -> None:
        """Update the playback tempo menu action state.

        Args:
            enabled: Whether playback tempo adjustment is enabled
        """
        if self.playback_tempo_action:
            self.playback_tempo_action.setChecked(enabled)

    def update_playback_mode_menu(self, mode: str | PlaybackMode) -> None:
        """Update the playback mode menu to reflect the current mode.

        Args:
            mode: The current playback mode ("one-shot", "loop", or "loop-reverse")
        """
        # Convert string to enum if necessary
        if isinstance(mode, str):
            try:
                mode = PlaybackMode(mode)
            except ValueError:
                logger.warning(f"Unknown playback mode '{mode}'")
                self.one_shot_action.setChecked(True)
                return

        match mode:
            case PlaybackMode.ONE_SHOT:
                self.one_shot_action.setChecked(True)
            case PlaybackMode.LOOP:
                self.loop_action.setChecked(True)
            case PlaybackMode.LOOP_REVERSE:
                self.loop_reverse_action.setChecked(True)
            case _:
                logger.warning(f"Unknown playback mode '{mode}'")
                self.one_shot_action.setChecked(True)
