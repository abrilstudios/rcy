from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QComboBox, QMessageBox, QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollBar, QSlider, QDialog, QTextBrowser, QInputDialog, QCheckBox
from PyQt6.QtGui import QAction, QActionGroup, QValidator, QIntValidator, QFont, QDesktopServices, QKeyEvent
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QUrl, QObject, QEvent
import os
import logging
from typing import Any
from config_manager import config
from ui.waveform import create_waveform_view
from error_handler import ErrorHandler
from segment_manager import get_segment_manager
import numpy as np

# UI Module imports
from ui.dialogs import KeyboardShortcutsDialog, AboutDialog, ExportCompletionDialog
from ui.menu_bar import MenuBarManager
from ui.shortcuts import KeyboardShortcutHandler
from ui.control_panel import ControlPanel
from ui.transport_controls import TransportControls

logger = logging.getLogger(__name__)

class RcyView(QMainWindow):
    measures_changed = pyqtSignal(int)
    threshold_changed = pyqtSignal(float)
    add_segment = pyqtSignal(float)
    remove_segment = pyqtSignal(float)
    play_segment = pyqtSignal(float)
    start_marker_changed = pyqtSignal(float)
    end_marker_changed = pyqtSignal(float)
    cut_requested = pyqtSignal(float, float)  # start_time, end_time
    
    # Ultra-fast segment shortcut mapping (class attribute for performance)
    SEGMENT_KEY_MAP = {
        Qt.Key.Key_1: 1, Qt.Key.Key_2: 2, Qt.Key.Key_3: 3, Qt.Key.Key_4: 4, Qt.Key.Key_5: 5,
        Qt.Key.Key_6: 6, Qt.Key.Key_7: 7, Qt.Key.Key_8: 8, Qt.Key.Key_9: 9, Qt.Key.Key_0: 10,
        Qt.Key.Key_Q: 11, Qt.Key.Key_W: 12, Qt.Key.Key_E: 13, Qt.Key.Key_R: 14, Qt.Key.Key_T: 15,
        Qt.Key.Key_Y: 16, Qt.Key.Key_U: 17, Qt.Key.Key_I: 18, Qt.Key.Key_O: 19, Qt.Key.Key_P: 20
    }

    def __init__(self, controller: Any) -> None:
        super().__init__()
        self.controller = controller
        self.start_marker: Any | None = None
        self.end_marker: Any | None = None
        self.start_marker_handle: Any | None = None
        self.end_marker_handle: Any | None = None
        self.dragging_marker: str | None = None

        # Active segment highlight
        self.active_segment_highlight: Any | None = None
        self.active_segment_highlight_right: Any | None = None
        self.current_active_segment: tuple[float | None, float | None] = (None, None)

        self.init_ui()
        self._setup_menu_bar()

        # Set up keyboard shortcut handler
        self.shortcut_handler = KeyboardShortcutHandler(
            on_play_pause=self.toggle_playback,
            on_segment_selected=self._play_segment_by_index
        )

        # Set key press handler for the entire window
        self.keyPressEvent = self.window_key_press

        # Get triangle dimensions from UI config using unified accessor
        marker_config = config.get_marker_handle_config()
        self.triangle_base = marker_config.get("width", 8)
        self.triangle_height = marker_config.get("height", 14)
        self.triangle_offset_y = marker_config.get("offsetY", 0)

        # Get marker snapping threshold from UI config using unified accessor
        self.snap_threshold = config.get_snap_threshold(0.025)
        logger.info("Marker snap threshold: %ss", self.snap_threshold)

        # Install event filter to catch key events at application level
        app = QApplication.instance()
        if app:
            app.installEventFilter(self.shortcut_handler)

    def toggle_playback_tempo(self, enabled: bool) -> None:
        """Toggle playback tempo adjustment on/off

        Args:
            enabled (bool): Whether playback tempo adjustment is enabled
        """
        logger.debug("Toggling playback tempo adjustment: %s")

        # Update menu action
        self.menu_manager.update_playback_tempo_action(enabled)

        # Update control panel
        target_bpm = self.control_panel.get_target_bpm()
        self.control_panel.set_playback_tempo(enabled, target_bpm)

        # Update controller
        self.controller.set_playback_tempo(enabled, target_bpm)
    
    def set_target_bpm(self, bpm: int) -> None:
        """Set the target BPM for playback tempo adjustment

        Args:
            bpm (int): Target BPM value
        """
        logger.debug("Setting target BPM to %s")

        # Update control panel
        enabled = self.control_panel.get_playback_tempo_enabled()
        self.control_panel.set_playback_tempo(enabled, bpm)

        # Update controller
        self.controller.set_playback_tempo(enabled, bpm)

    def update_playback_tempo_display(self, enabled: bool, target_bpm: int | None, ratio: float) -> None:
        """Update the playback tempo UI display

        Args:
            enabled (bool): Whether playback tempo adjustment is enabled
            target_bpm (int): Target tempo in BPM
            ratio (float): The playback ratio
        """
        logger.debug("DEBUG: update_playback_tempo_display called with:")
        logger.debug("DEBUG: - enabled=%s")
        logger.debug("DEBUG: - target_bpm=%s")
        logger.debug("DEBUG: - ratio=%s")

        # Ensure we have a valid target BPM
        if target_bpm is None:
            logger.debug("DEBUG: Warning - target_bpm is None, defaulting to 120")
            target_bpm = 120

        # Update control panel
        self.control_panel.set_playback_tempo(enabled, target_bpm)

        # Update menu action
        self.menu_manager.update_playback_tempo_action(enabled)

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar using MenuBarManager."""
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
            on_convert_to_mono=self.controller.convert_to_mono,
            on_show_shortcuts=lambda: KeyboardShortcutsDialog(self).exec(),
            on_show_about=lambda: AboutDialog(self).exec()
        )
        self.setMenuBar(self.menu_manager.create_menu_bar())

    def show_export_completion_dialog(self, export_stats: dict[str, Any] | None) -> None:
        """Show a dialog with export completion information

        Args:
            export_stats: Dictionary with export statistics
        """
        ExportCompletionDialog.show_dialog(export_stats, self)
            
    def export_segments(self) -> None:
        """Export segments to the selected directory"""
        directory = QFileDialog.getExistingDirectory(self,
                                                     config.get_string("dialogs", "exportDirectoryTitle"))
        if directory:
            # Export segments and get the export statistics
            export_stats = self.controller.export_segments(directory)
            
            # Show completion dialog
            self.show_export_completion_dialog(export_stats)
        else:
            # User canceled the export
            logger.debug("Export canceled by user")

    def save_as(self) -> None:
        # Implement save as functionality
        pass

    def init_ui(self) -> None:
        self.setWindowTitle(config.get_string("ui", "windowTitle"))
        self.setGeometry(100, 100, 800, 600)
        
        # Enable strong focus for keyboard events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Ensure window is actively focused
        self.activateWindow()
        self.raise_()

        # Set application-wide font
        app = QApplication.instance()
        if app:
            app.setFont(config.get_font('primary'))
            
        # Initialize internal flag to ensure markers always display
        self.always_show_markers = True

        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Set background and text color
        main_widget.setStyleSheet(f"background-color: {config.get_qt_color('background')}; color: {config.get_qt_color('textColor')};")
        
        self.setCentralWidget(main_widget)

        # Create control panel
        self.control_panel = ControlPanel()
        main_layout.addWidget(self.control_panel)

        # Connect control panel signals
        self.control_panel.measures_changed.connect(self.measures_changed.emit)
        self.control_panel.threshold_changed.connect(self.on_threshold_changed)
        self.control_panel.resolution_changed.connect(
            lambda res: self.controller.execute_command('set_resolution', resolution=res)
        )
        self.control_panel.playback_tempo_toggled.connect(self.toggle_playback_tempo)
        self.control_panel.target_bpm_changed.connect(self.set_target_bpm)

        # Create waveform visualization using PyQtGraph
        self.waveform_view = create_waveform_view()
        # Connect waveform view signals to appropriate handlers
        self.waveform_view.segment_clicked.connect(self.on_segment_clicked)
        self.waveform_view.marker_dragged.connect(self.on_marker_dragged)
        self.waveform_view.marker_released.connect(self.on_marker_released)
        
        # Connect segment manipulation signals
        self.waveform_view.add_segment.connect(lambda pos: self.on_add_segment(pos))
        self.waveform_view.remove_segment.connect(lambda pos: self.on_remove_segment(pos))
        
        # Use waveform_view as the primary widget
        self.waveform_widget = self.waveform_view
        
        # Flag for stereo display settings (still used in other parts of the app)
        self.stereo_display = config.get_setting("audio", "stereoDisplay", True)
        
        # Add the waveform widget to the layout
        main_layout.addWidget(self.waveform_widget)

        # Create scroll bar
        self.scroll_bar = QScrollBar(Qt.Orientation.Horizontal)
        self.scroll_bar.valueChanged.connect(self.controller.update_view)
        main_layout.addWidget(self.scroll_bar)

        # Create transport controls
        self.transport_controls = TransportControls()
        main_layout.addWidget(self.transport_controls)

        # Connect transport control signals
        self.transport_controls.split_measures_requested.connect(self.on_split_measures_clicked)
        self.transport_controls.split_transients_requested.connect(
            lambda: self.controller.execute_command('split_audio', method='transients')
        )
        self.transport_controls.cut_requested.connect(self.on_cut_button_clicked)
        self.transport_controls.zoom_in_requested.connect(
            lambda: self.controller.execute_command('zoom_in')
        )
        self.transport_controls.zoom_out_requested.connect(
            lambda: self.controller.execute_command('zoom_out')
        )
        

    def on_plot_click(self, event):
        logger.debug("on_plot_click")
        # Allow clicks in either waveform (top or bottom) for stereo display
        if event.inaxes not in [self.ax_left, self.ax_right]:
            return

        modifiers = QApplication.keyboardModifiers()
        logger.debug("    Modifiers value: %s")
        logger.debug("    Is Control: %s")
        logger.debug("    Is Shift: %s")
        logger.debug("    Is Alt: %s")
        logger.debug("    Is Meta: %s")
        
        # Using a more direct approach: if clicking on the first segment area, allow both marker and segment handling
        # Get click position details to help debug
        pos_info = ""
        if event.xdata is not None:
            # Get the view limits
            x_min, x_max = event.inaxes.get_xlim()
            # Determine if we're in first or last segment area
            # 'current_slices' may not exist until update_slices is called
            if getattr(self.controller, 'current_slices', None):
                first_slice = self.controller.current_slices[0]
                last_slice = self.controller.current_slices[-1]
                total_time = self.controller.model.total_time
                pos_info = (f"Click at x={event.xdata:.2f}, first_slice={first_slice:.2f}, "
                           f"last_slice={last_slice:.2f}, total={total_time:.2f}")
                logger.debug(pos_info)
        
        # PRIORITY 1: Check for keyboard modifiers first
        # ==================================================
        
        # Shift+Click to force play the first segment (for easier access)
        # This takes precedence over marker handling to ensure it always works
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            logger.debug("### Shift+Click detected - forcing first segment playback")
            # Always use a very small value to ensure first segment
            logger.debug("### Forcing first segment playback (0.01s)")
            self.play_segment.emit(0.01)
            return
            
        # Check for Ctrl+Alt (Option) combination for removing segments
        if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.AltModifier):
            logger.debug("Ctrl+Alt (Option) combination detected - removing segment at %s")
            self.remove_segment.emit(event.xdata)
            return
            
        # Check for Alt+Cmd (Meta) combination for removing segments
        if (modifiers & Qt.KeyboardModifier.AltModifier) and (modifiers & Qt.KeyboardModifier.MetaModifier):
            logger.debug("Alt+Cmd combination detected - removing segment at %s")
            self.remove_segment.emit(event.xdata)
            return
            
        # Add segment with Ctrl+Click
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            logger.debug("Ctrl detected - adding segment at %s")
            self.add_segment.emit(event.xdata)
            return
            
        # Add segment with Alt+Click
        if modifiers & Qt.KeyboardModifier.AltModifier:
            logger.debug("Alt detected - adding segment at %s")
            self.add_segment.emit(event.xdata)
            return
        
        # PRIORITY 2: Check for marker interaction - now with improved marker detection
        # ==================================================
        
        # Check if we're clicking near start marker (with enhanced detection)
        start_marker_x = self.start_marker.get_xdata()[0] if self.start_marker and self.start_marker.get_visible() else None
        logger.debug("Start marker at: %s")
        
        # Enhanced detection for start marker dragging - higher priority near the edge of waveform
        if start_marker_x is not None and abs(event.xdata - start_marker_x) < 0.1:
            logger.debug("Starting to drag start marker (enhanced detection)")
            self.dragging_marker = 'start'
            return
            
        # Check if we're clicking near end marker (with enhanced detection)
        end_marker_x = self.end_marker.get_xdata()[0] if self.end_marker and self.end_marker.get_visible() else None
        logger.debug("End marker at: %s")
        
        # Enhanced detection for end marker dragging
        if end_marker_x is not None and abs(event.xdata - end_marker_x) < 0.1:
            logger.debug("Starting to drag end marker (enhanced detection)")
            self.dragging_marker = 'end'
            return
            
        # Standard marker detection as fallback
        if self.is_near_marker(event.xdata, event.ydata, self.start_marker, self.start_marker_handle):
            logger.debug("Starting to drag start marker (standard detection)")
            self.dragging_marker = 'start'
            return
        elif self.is_near_marker(event.xdata, event.ydata, self.end_marker, self.end_marker_handle):
            logger.debug("Starting to drag end marker (standard detection)")
            self.dragging_marker = 'end'
            return
                
        # No modifiers - play segment at clicked position
        logger.debug("### Emitting play_segment signal with click position: %s")
        self.play_segment.emit(event.xdata)
            
    def is_near_marker(self, x, y, marker, marker_handle):
        """Check if coordinates are near the marker or its handle"""
        if marker is None or not marker.get_visible():
            logger.debug("Marker not visible or None")
            return False
        
        marker_x = marker.get_xdata()[0]  # Vertical lines have the same x for all points
        logger.debug("Checking marker at x=%s")
        
        # Very simple detection for marker:
        # If we're within a reasonable threshold of the marker, count as near
        # This is the original behavior that worked before
        total_time = self.controller.model.total_time
        threshold = total_time * 0.04  # 4% of total duration for hit detection
        
        is_near = abs(x - marker_x) < threshold
        if is_near:
            logger.debug("Click near marker (within threshold)")
        return is_near

    def on_threshold_changed(self, threshold: float) -> None:
        """Handle threshold changes from control panel.

        Args:
            threshold: Threshold value (0.0-1.0)
        """
        # Dispatch via command pattern
        self.controller.execute_command('set_threshold', threshold=threshold)

    def update_slices(self, slices: list[float]) -> None:
        logger.debug("Convert slice points to times")
        slice_times = [slice_point / self.controller.model.sample_rate for slice_point in slices]
        
        # Get current marker positions
        start_pos, end_pos = self.waveform_view.get_marker_positions()
        
        # Always get the current file's total time
        total_time = self.controller.model.total_time
        
        # Use default values if markers are not set
        if start_pos is None:
            start_pos = 0
        if end_pos is None:
            end_pos = total_time
        
        logger.debug("Marker positions before update - start: %s, end: %s")
        
        # Validate marker positions against current file boundaries
        if start_pos < 0:
            start_pos = 0
        
        if end_pos > total_time:
            end_pos = total_time
            
        # If end marker is too close to start or exceeds file length, adjust it
        if abs(end_pos - start_pos) < 0.1 or end_pos > total_time:
            logger.debug("End marker too close to start marker or beyond file end, adjusting: %s -> %s")
            end_pos = total_time
        
        # Set marker positions
        self.waveform_view.set_start_marker(start_pos)
        self.waveform_view.set_end_marker(end_pos)
        
        # Update the waveform view with slices and total time
        self.waveform_view.update_slices(slice_times, total_time)
        
        # Update controller's internal marker position tracking without triggering tempo updates
        # This is different from on_start/end_marker_changed which should only be called for user dragging
        self.controller.start_marker_pos = start_pos
        self.controller.end_marker_pos = end_pos
        # Also update tempo_controller's marker positions so tempo calculations work
        self.controller.tempo_ctrl.start_marker_pos = start_pos
        self.controller.tempo_ctrl.end_marker_pos = end_pos
        
        # Store the current slices in the controller
        self.controller.current_slices = slice_times
        logger.debug("Debugging: Updated current_slices in controller: %s")

    def on_measures_changed(self) -> None:
        """Handle changes to the measures input field and update controller"""
        text = self.measures_input.text()
        validator = self.measures_input.validator()
        state, _, _ = validator.validate(text, 0)

        if state == QValidator.State.Acceptable:
            num_measures = int(text)
            logger.debug("Measure count changed to %s")
            # Emitting signal will trigger controller.on_measures_changed
            self.measures_changed.emit(num_measures)
        else:
            # Reset to controller's current value or default to 1
            current_measures = getattr(self.controller, 'num_measures', 1)
            self.measures_input.setText(str(current_measures))
            logger.debug("Invalid measure count, reset to %s")

    def update_tempo(self, tempo: float) -> None:
        """Update the tempo display.

        Args:
            tempo: Tempo in BPM
        """
        logger.debug("DEBUG: update_tempo called with tempo=%s")
        self.control_panel.update_tempo_display(tempo)
        logger.debug("DEBUG: tempo_display updated to '%s BPM'")

    def on_button_release(self, event):
        """Handle button release event to stop dragging"""
        if self.dragging_marker:
            # Emit a signal about the final position
            if self.dragging_marker == 'start':
                self.start_marker_changed.emit(self.start_marker.get_xdata()[0])
            elif self.dragging_marker == 'end':
                self.end_marker_changed.emit(self.end_marker.get_xdata()[0])
            
            self.dragging_marker = None
    
    def on_motion_notify(self, event):
        """Handle mouse movement for dragging markers"""
        if not self.dragging_marker or event.inaxes not in [self.ax_left, self.ax_right]:
            return
        
        # Update marker position
        if self.dragging_marker == 'start':
            # Ensure start marker doesn't go past end marker
            if self.end_marker.get_visible():
                end_x = self.end_marker.get_xdata()[0]
                if event.xdata >= end_x:
                    return
            self.set_start_marker(event.xdata)
        elif self.dragging_marker == 'end':
            # Ensure end marker doesn't go before start marker
            if self.start_marker.get_visible():
                start_x = self.start_marker.get_xdata()[0]
                if event.xdata <= start_x:
                    return
            self.set_end_marker(event.xdata)
        
        self.canvas.draw()
    
    def set_start_marker(self, x_pos: float) -> None:
        """Set the position of the start marker"""
        # Delegate to the waveform view component
        self.waveform_view.set_start_marker(x_pos)

    def set_end_marker(self, x_pos: float) -> None:
        """Set the position of the end marker"""
        # Delegate to the waveform view component
        self.waveform_view.set_end_marker(x_pos)
    
    def get_marker_positions(self) -> tuple[float | None, float | None]:
        """Get the positions of both markers, or None if not visible"""
        # Delegate to the waveform view component
        return self.waveform_view.get_marker_positions()
        
    def window_key_press(self, event: QKeyEvent) -> None:
        """Handle Qt key press events for the entire window"""
        key = event.key()
        
        # Spacebar - toggle playback
        if key == Qt.Key.Key_Space:
            self.toggle_playback()
            return
        
        # Segment shortcuts - ultra-fast lookup
        segment_index = self._get_segment_index_from_key(key)
        if segment_index is not None:
            self._play_segment_by_index(segment_index)
            return
                
        # Default processing
        super().keyPressEvent(event)
    
    def _get_segment_index_from_key(self, key: Qt.Key) -> int | None:
        """Ultra-fast key to segment index mapping. Returns 1-based index or None."""
        return self.SEGMENT_KEY_MAP.get(key)
    
    def _play_segment_by_index(self, segment_index: int) -> None:
        """Ultra-fast segment playback using SegmentManager O(1) lookup.

        Respects marker positions (locators) by clamping segment boundaries,
        similar to ReCycle's locator behavior.
        """
        segment_manager = get_segment_manager()

        # Get segment boundaries directly from SegmentManager
        segment_bounds = segment_manager.get_segment_by_index(segment_index)
        if not segment_bounds:
            return  # Invalid segment index

        start_time, end_time = segment_bounds

        # Get marker positions (locators) and clamp segment boundaries
        marker_start, marker_end = self.get_marker_positions()
        if marker_start is not None:
            start_time = max(start_time, marker_start)
        if marker_end is not None:
            end_time = min(end_time, marker_end)

        # Highlight the segment in the UI (use clamped boundaries)
        self.highlight_active_segment(start_time, end_time)

        # Play the segment (with clamped boundaries)
        self.controller.model.play_segment(start_time, end_time)
        
    def toggle_playback(self) -> None:
        """Toggle playback between start and stop"""
        if self.controller.model.is_playing:
            # If playing, stop playback
            logger.debug("Toggle: Stopping playback")
            self.controller.stop_playback()
        else:
            # If not playing, find the most appropriate segment to play
            
            # First, check for markers
            start_pos, end_pos = self.get_marker_positions()
            if start_pos is not None and end_pos is not None:
                # Use markers if both are set
                logger.debug("Toggle: Playing from markers %s to %s with mode: %s")
                
                # Highlight the active segment in the view
                self.highlight_active_segment(start_pos, end_pos)
                
                # Store the current segment in the controller for looping
                self.controller.current_segment = (start_pos, end_pos)
                self.controller.is_playing_reverse = False
                
                self.controller.model.play_segment(start_pos, end_pos)
                return
                
            # If no markers, find the segment that would be clicked
            # We'll use the center of the current view as the "virtual click" position
            center_pos = self.waveform_view.get_view_center()
            
            # Emulate a click at the center of the current view
            logger.debug("Toggle: Emulating click at center of view: %s")
            self.controller.play_segment(center_pos)
    
    def on_key_press(self, event):
        """Handle key press events"""
        # Print in detail what key was pressed
        logger.debug("Key pressed: %s")
        logger.debug("Key modifiers: %s")
        
        # Handle spacebar for play/stop toggle
        if event.key == ' ' or event.key == 'space':
            logger.debug("Spacebar detected! Toggling playback...")
            self.toggle_playback()
            return
            
        # 'r' key handlers removed - no longer needed for clearing markers
            
        # Allow key presses in either waveform for stereo display
        if event.inaxes not in [self.ax_left, self.ax_right]:
            return
            
        # 'c' key no longer needed for clearing markers
        # Can be repurposed for other functionality
    
    def on_segment_clicked(self, x_position: float) -> None:
        """Handle segment click events from waveform view."""
        logger.debug("Segment clicked at %ss")
        self.play_segment.emit(x_position)

    def on_marker_dragged(self, marker_type: str, position: float) -> None:
        """Handle marker drag events from waveform view."""
        logger.debug("Marker %s dragged to %ss")
        self.dragging_marker = marker_type

    def on_marker_released(self, marker_type: str, position: float) -> None:
        """Handle marker release events from waveform view."""
        logger.debug("Marker %s released at %ss")
        if marker_type == 'start':
            self.start_marker_changed.emit(position)
        else:
            self.end_marker_changed.emit(position)
        self.dragging_marker = None
            
    def on_cut_button_clicked(self):
        """Handle the Cut button click"""
        # Get marker positions
        start_pos, end_pos = self.get_marker_positions()
        
        # Check if both markers are set
        if start_pos is None or end_pos is None:
            QMessageBox.warning(self, 
                                config.get_string("dialogs", "cannotCutTitle"), 
                                config.get_string("dialogs", "cannotCutMessage"))
            return
        
        # Briefly highlight the selection
        self.waveform_view.highlight_segment(start_pos, end_pos, temporary=True)
            
        # Confirm the action
        reply = QMessageBox.question(self,
                                    config.get_string("dialogs", "confirmCutTitle"),
                                    config.get_string("dialogs", "confirmCutMessage"),
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        # Remove highlight
        self.waveform_view.clear_active_segment_highlight()
                                    
        if reply == QMessageBox.StandardButton.Yes:
            # Emit the signal to request cutting
            self.cut_requested.emit(start_pos, end_pos)
            
            # Clear the markers after cutting
            self.clear_markers()
    
    def _create_marker_handles(self):
        """Create directional triangle handles for both markers"""
        # Create empty triangles initially - they'll be positioned properly later
        empty_triangle = np.array([[0, 0], [0, 0], [0, 0]])
        
        # Set marker properties with hint about the marker type
        # Improved visibility with higher alpha and zorder
        start_marker_props = {
            'closed': True,
            'color': config.get_qt_color('startMarker'),
            'fill': True,
            'alpha': 1.0,  # Fully opaque
            'visible': True,  # Always start visible
            'zorder': 100,  # Ensure triangles are above all other elements
            'label': 'start_marker_handle',  # Add label for debugging/identification
            'linewidth': 1.5  # Thicker outline
        }
        
        end_marker_props = {
            'closed': True,
            'color': config.get_qt_color('endMarker'),
            'fill': True,
            'alpha': 1.0,  # Fully opaque
            'visible': True,  # Always start visible
            'zorder': 100,  # Ensure triangles are above all other elements
            'label': 'end_marker_handle',  # Add label for debugging/identification
            'linewidth': 1.5  # Thicker outline
        }
        
        # Create the start marker handle (right-pointing triangle)
        if self.start_marker_handle is not None:
            try:
                self.start_marker_handle.remove()
            except:
                logger.warning("Warning: Could not remove existing start marker handle")
                
        self.start_marker_handle = Polygon(empty_triangle, **start_marker_props)
        self.ax.add_patch(self.start_marker_handle)
        logger.debug("Created start marker handle (improved visibility)")
        
        # Create the end marker handle (left-pointing triangle)
        if self.end_marker_handle is not None:
            try:
                self.end_marker_handle.remove()
            except:
                logger.warning("Warning: Could not remove existing end marker handle")
                
        self.end_marker_handle = Polygon(empty_triangle, **end_marker_props)
        self.ax.add_patch(self.end_marker_handle)
        logger.debug("Created end marker handle (improved visibility)")

    def _update_marker_handle(self, marker_type):
        """Update the position of a marker's triangle handle"""
        # Get the current axis dimensions to calculate pixel-based positions
        x_min, x_max = self.ax.get_xlim()
        y_min, y_max = self.ax.get_ylim()
        
        # Set fixed data sizes for triangles instead of scaling with view
        # This keeps triangles the same size regardless of zoom level
        # Using a fixed ratio of the total time for consistent scale
        total_time = self.controller.model.total_time
        
        # Make the triangles an appropriate size for visibility and interaction
        # Balanced sizes relative to the total audio duration
        triangle_height_data = total_time * 0.02  # 2% of total duration
        triangle_base_half_data = total_time * 0.015  # 1.5% of total duration
        logger.debug("Triangle size: height=%s, half-base=%s, total_time=%s")
        
        if marker_type == 'start':
            marker = self.start_marker
            handle = self.start_marker_handle
            logger.debug("Updating start marker handle")
        else:  # end marker
            marker = self.end_marker
            handle = self.end_marker_handle
            logger.debug("Updating end marker handle")
            
        # Ensure marker and handle exist
        if marker is None or handle is None:
            logger.debug("Marker or handle is None for %s")
            return
        
        # Force marker to be visible
        if not marker.get_visible():
            logger.debug("Forcing %s marker to be visible")
            marker.set_visible(True)
            
        # Get marker position
        marker_x = marker.get_xdata()[0]
        logger.debug("%s marker position: %s")
        
        # Position triangle at the bottom of the waveform
        # No offset from the bottom - triangles should be aligned with the bottom line
        base_y = y_min  # Place triangles exactly at the bottom of the waveform
        
        # Create right triangle coordinates according to spec
        if marker_type == 'start':
            # Start marker: Right triangle that points RIGHT (→)
            # Make a more visible triangle for the start marker
            triangle_coords = np.array([
                [marker_x, base_y],  # Bottom center point (aligned with marker)
                [marker_x + triangle_base_half_data, base_y],  # Bottom-right (right angle corner)
                [marker_x, base_y + triangle_height_data]  # Top center point (aligned with marker)
            ])
        else:  # end marker
            # End marker: Right triangle that points LEFT (←)
            # Make a more visible triangle for the end marker
            triangle_coords = np.array([
                [marker_x, base_y],  # Bottom center point (aligned with marker)
                [marker_x - triangle_base_half_data, base_y],  # Bottom-left (right angle corner)
                [marker_x, base_y + triangle_height_data]  # Top center point (aligned with marker)
            ])
        
        # Update the triangle
        handle.set_xy(triangle_coords)
        handle.set_visible(True)
        handle.set_zorder(100)  # Ensure triangles are always on top
        logger.debug("Updated %s marker handle: visible=%s, zorder=%s")
    
    def clear_markers(self):
        """Reset markers to file boundaries instead of hiding them"""
        # Reset markers to file boundaries
        total_time = self.controller.model.total_time

        # Use the waveform view component to reset markers
        self.waveform_view.set_start_marker(0.0)
        self.waveform_view.set_end_marker(total_time)

        # Let controller know about the reset
        self.controller.on_start_marker_changed(0.0)
        self.controller.on_end_marker_changed(total_time)

        logger.debug("Reset markers to file boundaries (0.0s to %ss)")
    
    def update_plot(self, time, data_left, data_right=None, is_stereo=False):
        """Update the plot with time and audio data.
        For mono files, data_right can be None or same as data_left.
        For stereo files, data_left and data_right will be different channels.
        """
        # Delegate to the waveform view component
        self.waveform_view.update_plot(time, data_left, data_right, is_stereo=is_stereo)
    
    def _update_marker_visibility(self, ax, start_marker, end_marker):
        """Update marker visibility based on current view
        Note: Markers are now always visible, but we keep this method to make sure
        their triangle handles are updated correctly.
        """
        if start_marker is None or end_marker is None:
            logger.warning("Warning: One of the markers is None in _update_marker_visibility")
            return
            
        x_min, x_max = ax.get_xlim()
        
        # Always ensure the marker lines themselves are visible
        if not start_marker.get_visible():
            logger.debug("Forcing start marker to be visible")
            start_marker.set_visible(True)
            
        if not end_marker.get_visible():
            logger.debug("Forcing end marker to be visible")
            end_marker.set_visible(True)
            
        # Debug marker positions
        start_pos = start_marker.get_xdata()[0]
        end_pos = end_marker.get_xdata()[0]
        logger.debug("Marker positions - start: %s, end: %s")
        
        # Force update triangle handles regardless of view
        if self.start_marker_handle and start_marker == self.start_marker:
            self.start_marker_handle.set_visible(True)
            self._update_marker_handle('start')
            logger.debug("Updated start marker handle")
            
        if self.end_marker_handle and end_marker == self.end_marker:
            self.end_marker_handle.set_visible(True)
            self._update_marker_handle('end')
            logger.debug("Updated end marker handle")

    def update_scroll_bar(self, visible_time, total_time):
        # Block signals to prevent recursive updates
        proportion = visible_time / total_time if total_time > 0 else 0.0
        old_state = self.scroll_bar.blockSignals(True)
        try:
            self.scroll_bar.setPageStep(int(proportion * 100))
        finally:
            self.scroll_bar.blockSignals(old_state)

    def get_scroll_position(self):
        return self.scroll_bar.value()
        
    def highlight_active_segment(self, start_time: float, end_time: float) -> None:
        """Highlight the currently playing segment"""
        logger.debug("Highlighting active segment: %ss to %ss")

        # Store current segment
        self.current_active_segment = (start_time, end_time)

        # Delegate to the waveform view component
        self.waveform_view.highlight_active_segment(start_time, end_time)

    def clear_active_segment_highlight(self) -> None:
        """Remove the active segment highlight"""
        # Delegate to the waveform view component
        self.waveform_view.clear_active_segment_highlight()

        # Reset active segment tracking
        self.current_active_segment = (None, None)

    def load_preset(self, preset_id: str) -> None:
        """Load the selected preset"""
        success = self.controller.load_preset(preset_id)
        if not success:
            ErrorHandler.show_error(
                f"Failed to load preset: {preset_id}",
                config.get_string("dialogs", "errorTitle"),
                self
            )
                                
    def update_playback_mode_menu(self, mode: str) -> None:
        """Update the playback mode menu to reflect the current mode

        Args:
            mode (str): The current playback mode
        """
        self.menu_manager.update_playback_mode_menu(mode)
    
    def set_playback_mode(self, mode: str) -> None:
        """Set the playback mode in the controller

        Args:
            mode (str): The playback mode to set
        """
        logger.debug("View set_playback_mode: %s")
        if self.controller:
            self.controller.set_playback_mode(mode)
                                
    def on_add_segment(self, position: float) -> None:
        """Handle add_segment signal from waveform view"""
        logger.debug("RcyView.on_add_segment(%s)")
        try:
            self.add_segment.emit(position)
        except Exception as e:
            ErrorHandler.handle_exception(e, context="Adding segment", parent=self)

    def on_remove_segment(self, position: float) -> None:
        """Handle remove_segment signal from waveform view"""
        logger.debug("RcyView.on_remove_segment(%s)")
        try:
            self.remove_segment.emit(position)
        except Exception as e:
            ErrorHandler.handle_exception(e, context="Removing segment", parent=self)
    
    def load_session_file(self) -> None:
        """Load an existing RCY session file"""
        # Note: This is a placeholder for future implementation
        # For now, just show a message that this feature is coming
        QMessageBox.information(self,
                              "Coming Soon",
                              "Loading session files will be implemented in a future version.\n\n"
                              "Currently, presets are used as sessions.")
    
    def import_audio_file(self) -> None:
        """Import a new audio file"""
        filename, _ = QFileDialog.getOpenFileName(self,
            "Import Audio File",
            "",
            config.get_string("dialogs", "audioFileFilter"))
        if filename:
            self.controller.load_audio_file(filename)
        else:
            ErrorHandler.show_error(
                config.get_string("dialogs", "errorLoadingFile"),
                config.get_string("dialogs", "errorTitle"),
                self
            )
                                
    # Keep for backward compatibility with any code that might call it
    def load_audio_file(self):
        """Deprecated - use import_audio_file instead"""
        self.import_audio_file()

    def on_split_measures_clicked(self):
        """Handle the Split by Measures button click by using the current dropdown selection"""
        # Get the current resolution from the control panel
        resolution_value = self.control_panel.get_resolution()

        # Trigger the split with the current resolution
        # Dispatch via command
        self.controller.execute_command(
            'split_audio', method='measures', measure_resolution=resolution_value
        )
