from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QComboBox, QMessageBox, QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollBar, QSlider, QDialog, QTextBrowser, QInputDialog, QCheckBox
from PyQt6.QtGui import QAction, QActionGroup, QValidator, QIntValidator, QFont, QDesktopServices
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QUrl
import os
from config_manager import config
from waveform_view import create_waveform_view
from error_handler import ErrorHandler
import numpy as np

class RcyView(QMainWindow):
    measures_changed = pyqtSignal(int)
    threshold_changed = pyqtSignal(float)
    add_segment = pyqtSignal(float)
    remove_segment = pyqtSignal(float)
    play_segment = pyqtSignal(float)
    start_marker_changed = pyqtSignal(float)
    end_marker_changed = pyqtSignal(float)
    cut_requested = pyqtSignal(float, float)  # start_time, end_time

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.start_marker = None
        self.end_marker = None
        self.start_marker_handle = None
        self.end_marker_handle = None
        self.dragging_marker = None
        
        # Active segment highlight
        self.active_segment_highlight = None
        self.active_segment_highlight_right = None
        self.current_active_segment = (None, None)  # (start, end) times of currently active segment
        
        self.init_ui()
        self.create_menu_bar()
        
        # Set key press handler for the entire window
        self.keyPressEvent = self.window_key_press
        
        # Get triangle dimensions from UI config
        self.triangle_base = config.get_ui_setting("markerHandles", "width", 16)
        self.triangle_height = config.get_ui_setting("markerHandles", "height", 10)
        self.triangle_offset_y = config.get_ui_setting("markerHandles", "offsetY", 0)
        
        # Get marker snapping threshold from UI config
        self.snap_threshold = config.get_ui_setting("markerSnapping", "snapThreshold", 0.025)
        print(f"Marker snap threshold: {self.snap_threshold}s")
        
        # Install event filter to catch key events at application level
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
            
    def eventFilter(self, obj, event):
        """Application-wide event filter to catch key events"""
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Space:
                print("Spacebar detected via event filter! Toggling playback...")
                self.toggle_playback()
                return True
        return super().eventFilter(obj, event)
        
    def toggle_playback_tempo(self, enabled):
        """Toggle playback tempo adjustment on/off
        
        Args:
            enabled (bool): Whether playback tempo adjustment is enabled
        """
        print(f"Toggling playback tempo adjustment: {enabled}")
        
        # Update menu action
        self.playback_tempo_action.setChecked(enabled)

        # Update checkbox
        self.playback_tempo_checkbox.setChecked(enabled)

        # Get the current target BPM from the dropdown
        target_bpm = None
        current_index = self.playback_tempo_combo.currentIndex()
        if current_index >= 0:
            target_bpm = self.playback_tempo_combo.itemData(current_index)

        # Update controller
        self.controller.set_playback_tempo(enabled, target_bpm)
    
    def set_target_bpm(self, bpm):
        """Set the target BPM for playback tempo adjustment
        
        Args:
            bpm (int): Target BPM value
        """
        print(f"Setting target BPM to {bpm}")
        
        # Update dropdown
        for i in range(self.playback_tempo_combo.count()):
            if self.playback_tempo_combo.itemData(i) == bpm:
                self.playback_tempo_combo.setCurrentIndex(i)
                break
        
        # Get current enabled state from checkbox
        enabled = self.playback_tempo_checkbox.isChecked()
        
        # Update controller
        self.controller.set_playback_tempo(enabled, bpm)
    
    def on_playback_tempo_changed(self, index):
        """Handle changes to the playback tempo dropdown
        
        Args:
            index (int): Index of the selected item
        """
        if index < 0:
            return
            
        # Get the selected BPM
        bpm = self.playback_tempo_combo.itemData(index)
        print(f"Playback tempo changed to {bpm} BPM")
        
        # Update the custom BPM input to match the selected value
        self.target_bpm_input.setText(str(bpm))
        
        # Get current enabled state
        enabled = self.playback_tempo_checkbox.isChecked()
        
        # Update controller
        self.controller.set_playback_tempo(enabled, bpm)
        
    def on_target_bpm_input_changed(self):
        """Handle changes to the custom BPM input field"""
        text = self.target_bpm_input.text()
        if not text:
            return
            
        # Validate input
        validator = self.target_bpm_input.validator()
        state, _, _ = validator.validate(text, 0)
        
        if state == QValidator.State.Acceptable:
            # Convert to integer
            bpm = int(text)
            print(f"Custom BPM set to {bpm}")
            
            # Get current enabled state
            enabled = self.playback_tempo_checkbox.isChecked()
            
            # Update controller
            self.controller.set_playback_tempo(enabled, bpm)
            
            # Ensure the checkbox is enabled since the user wants to use a custom tempo
            if not enabled:
                self.playback_tempo_checkbox.setChecked(True)
        else:
            # Reset to a default value if invalid
            self.target_bpm_input.setText("120")
    
    def update_playback_tempo_display(self, enabled, target_bpm, ratio):
        """Update the playback tempo UI display
        
        Args:
            enabled (bool): Whether playback tempo adjustment is enabled
            target_bpm (int): Target tempo in BPM
            ratio (float): The playback ratio
        """
        print(f"DEBUG: update_playback_tempo_display called with:")
        print(f"DEBUG: - enabled={enabled}")
        print(f"DEBUG: - target_bpm={target_bpm}")
        print(f"DEBUG: - ratio={ratio}")
        
        # Ensure we have a valid target BPM
        if target_bpm is None:
            print("DEBUG: Warning - target_bpm is None, defaulting to 120")
            target_bpm = 120
        
        # Update checkbox - IMPORTANT: Force the checkbox to match the 'enabled' parameter
        print(f"DEBUG: Setting checkbox to {enabled}")
        self.playback_tempo_checkbox.setChecked(enabled)
        
        # Update custom BPM input - IMPORTANT: Always update this field
        self.target_bpm_input.setText(str(target_bpm))
        print(f"DEBUG: Updated target_bpm_input text to {target_bpm}")
            
        # Update dropdown to show the target BPM
        # First try exact match
        dropdown_updated = False
        for i in range(self.playback_tempo_combo.count()):
            if self.playback_tempo_combo.itemData(i) == target_bpm:
                self.playback_tempo_combo.setCurrentIndex(i)
                dropdown_updated = True
                print(f"DEBUG: Found exact match in dropdown at index {i}")
                break
                
        # If no exact match, find the closest value in the dropdown
        if not dropdown_updated:
            print(f"DEBUG: No exact match found in dropdown for BPM {target_bpm}")
            
            closest_index = 0
            closest_diff = abs(self.playback_tempo_combo.itemData(0) - target_bpm)
            
            # Find the closest BPM value in the dropdown
            for i in range(1, self.playback_tempo_combo.count()):
                diff = abs(self.playback_tempo_combo.itemData(i) - target_bpm)
                if diff < closest_diff:
                    closest_diff = diff
                    closest_index = i
            
            # Set to closest value
            self.playback_tempo_combo.setCurrentIndex(closest_index)
            print(f"DEBUG: Set dropdown to closest match at index {closest_index} (value: {self.playback_tempo_combo.itemData(closest_index)})")
        
        # Update menu action
        self.playback_tempo_action.setChecked(enabled)

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu(config.get_string("menus", "file"))

        # Open action
        open_action = QAction("Open Session", self)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Open a saved session file')
        open_action.triggered.connect(self.load_session_file)
        file_menu.addAction(open_action)
        
        # Import Audio action
        import_action = QAction("Import Audio", self)
        import_action.setShortcut('Ctrl+I')
        import_action.setStatusTip('Import a new audio file')
        import_action.triggered.connect(self.import_audio_file)
        file_menu.addAction(import_action)
        
        # Open Preset submenu
        presets_menu = file_menu.addMenu("Open Preset")
        self.populate_presets_menu(presets_menu)

        # Export action
        export_action = QAction(config.get_string("menus", "export"), self)
        export_action.setShortcut('Ctrl+E')
        export_action.setStatusTip('Export segments and SFZ file')
        export_action.triggered.connect(self.export_segments)
        file_menu.addAction(export_action)

        # Save As action
        save_as_action = QAction(config.get_string("menus", "saveAs"), self)
        save_as_action.triggered.connect(self.save_as)
        file_menu.addAction(save_as_action)
        
        # Options menu
        options_menu = menubar.addMenu("Options")
        
        # Playback Tempo submenu
        playback_tempo_menu = options_menu.addMenu("Playback Tempo")
        
        # Enable/disable playback tempo adjustment
        self.playback_tempo_action = QAction("Enable Tempo Adjustment", self)
        self.playback_tempo_action.setCheckable(True)
        self.playback_tempo_action.triggered.connect(self.toggle_playback_tempo)
        playback_tempo_menu.addAction(self.playback_tempo_action)
        
        # Add separator
        playback_tempo_menu.addSeparator()
        
        # Add common BPM choices
        common_bpms = [50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 160, 170, 180]
        for bpm in common_bpms:
            bpm_action = QAction(f"{bpm} BPM", self)
            bpm_action.triggered.connect(lambda checked, bpm=bpm: self.set_target_bpm(bpm))
            playback_tempo_menu.addAction(bpm_action)
        
        # Playback Mode submenu
        playback_mode_menu = options_menu.addMenu("Playback Mode")
        
        # Create action group for radio button behavior
        playback_mode_group = QActionGroup(self)
        playback_mode_group.setExclusive(True)
        
        # Add playback mode options with radio buttons
        self.one_shot_action = QAction("One-Shot", self)
        self.one_shot_action.setCheckable(True)
        self.one_shot_action.triggered.connect(lambda: self.set_playback_mode("one-shot"))
        playback_mode_group.addAction(self.one_shot_action)
        playback_mode_menu.addAction(self.one_shot_action)
        
        self.loop_action = QAction("Loop", self)
        self.loop_action.setCheckable(True)
        self.loop_action.triggered.connect(lambda: self.set_playback_mode("loop"))
        playback_mode_group.addAction(self.loop_action)
        playback_mode_menu.addAction(self.loop_action)
        
        self.loop_reverse_action = QAction("Loop and Reverse", self)
        self.loop_reverse_action.setCheckable(True)
        self.loop_reverse_action.triggered.connect(lambda: self.set_playback_mode("loop-reverse"))
        playback_mode_group.addAction(self.loop_reverse_action)
        playback_mode_menu.addAction(self.loop_reverse_action)
        
        # Set initial selection to one-shot (default)
        # The controller will update this later if needed
        self.one_shot_action.setChecked(True)
        
        # Help menu
        help_menu = menubar.addMenu(config.get_string("menus", "help"))
        
        # Keyboard shortcuts action
        shortcuts_action = QAction(config.get_string("menus", "keyboardShortcuts"), self)
        shortcuts_action.triggered.connect(self.show_keyboard_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        # About action
        about_action = QAction(config.get_string("menus", "about"), self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_export_completion_dialog(self, export_stats):
        """Show a dialog with export completion information
        
        Args:
            export_stats: Dictionary with export statistics
        """
        if not export_stats:
            return
            
        # Format time signature for display
        time_sig = f"{export_stats['time_signature'][0]}/{export_stats['time_signature'][1]}" if export_stats['time_signature'] else "4/4"
        
        # Create completion dialog with export statistics
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Export Complete")
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        # Build the message text
        message = f"Successfully exported {export_stats['segment_count']} segments.\n\n"
        message += f"SFZ Instrument: {os.path.basename(export_stats['sfz_path'])}\n"
        message += f"MIDI Sequence: {os.path.basename(export_stats['midi_path'])}\n\n"
        message += f"Time Signature: {time_sig}\n"
        
        # Show tempo information, accounting for tempo adjustment
        if export_stats.get('playback_tempo_enabled', False):
            message += f"Source Tempo: {export_stats['source_bpm']:.1f} BPM\n"
            message += f"Adjusted Tempo (MIDI): {export_stats['tempo']:.1f} BPM\n"
        else:
            message += f"Tempo: {export_stats['tempo']:.1f} BPM\n"
            
        message += f"Duration: {export_stats['duration']:.2f} seconds\n"
        message += f"\nFiles saved to:\n{export_stats['directory']}"
        
        msg_box.setText(message)
        
        # Add a button to open the export directory
        open_dir_button = msg_box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        close_button = msg_box.addButton(QMessageBox.StandardButton.Close)
        
        # Show the dialog
        msg_box.exec()
        
        # Check if the user clicked "Open Folder"
        if msg_box.clickedButton() == open_dir_button:
            # Open the directory using the platform's file manager
            QDesktopServices.openUrl(QUrl.fromLocalFile(export_stats['directory']))
            
    def export_segments(self):
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
            print("Export canceled by user")

    def save_as(self):
        # Implement save as functionality
        pass

    def init_ui(self):
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

        # create top bar info row
        info_layout = QHBoxLayout()
        slice_layout = QHBoxLayout()

        ## Number of Measures Input
        self.measures_label = QLabel(config.get_string("labels", "numMeasures"))
        self.measures_input = QLineEdit("1")
        self.measures_input.setValidator(QIntValidator(1, 1000))
        self.measures_input.editingFinished.connect(self.on_measures_changed)
        info_layout.addWidget(self.measures_label)
        info_layout.addWidget(self.measures_input)

        ## Tempo Display
        self.tempo_label = QLabel(config.get_string("labels", "tempo"))
        self.tempo_display = QLineEdit("N/A")
        self.tempo_display.setReadOnly(True)
        info_layout.addWidget(self.tempo_label)
        info_layout.addWidget(self.tempo_display)
        
        ## Playback Tempo Controls
        # Create a horizontal layout for playback tempo
        playback_tempo_layout = QHBoxLayout()
        
        # Create checkbox for enabling/disabling
        self.playback_tempo_checkbox = QCheckBox("Tempo Adjust:")
        self.playback_tempo_checkbox.setChecked(False)
        self.playback_tempo_checkbox.toggled.connect(self.toggle_playback_tempo)
        playback_tempo_layout.addWidget(self.playback_tempo_checkbox)
        
        # Create dropdown for target BPM
        self.playback_tempo_combo = QComboBox()
        common_bpms = [80, 90, 100, 110, 120, 130, 140, 160, 170, 180]
        for bpm in common_bpms:
            self.playback_tempo_combo.addItem(f"{bpm} BPM", bpm)
        self.playback_tempo_combo.currentIndexChanged.connect(self.on_playback_tempo_changed)
        playback_tempo_layout.addWidget(self.playback_tempo_combo)
        
        # Create free-form input for target BPM
        self.target_bpm_input = QLineEdit()
        self.target_bpm_input.setValidator(QIntValidator(40, 300))  # Reasonable tempo range
        self.target_bpm_input.setPlaceholderText("Custom BPM")
        self.target_bpm_input.editingFinished.connect(self.on_target_bpm_input_changed)
        self.target_bpm_input.setMaximumWidth(80)
        playback_tempo_layout.addWidget(self.target_bpm_input)
        
        # Add the playback tempo layout to the info layout
        info_layout.addLayout(playback_tempo_layout)

        ## Load Button
        #self.load_button = QPushButton("Load Audio")
        #self.load_button.clicked.connect(self.load_audio_file)
        #info_layout.addWidget(self.load_button)

        ## add split buttons
        self.split_measures_button = QPushButton(config.get_string("buttons", "splitMeasures"))
        self.split_measures_button.clicked.connect(self.on_split_measures_clicked)

        self.split_transients_button = QPushButton(config.get_string("buttons", "splitTransients"))
        self.split_transients_button.clicked.connect(lambda: self.controller.split_audio('transients'))

        # Add measure resolution dropdown
        self.measure_resolution_combo = QComboBox()
        self.measure_resolutions = config.get_string("labels", "measureResolutions")
        
        # Add each resolution option to the dropdown
        for resolution in self.measure_resolutions:
            self.measure_resolution_combo.addItem(resolution["label"])
        
        # Set default selection to the Quarter Note (4) option
        default_index = next((i for i, res in enumerate(self.measure_resolutions) if res["value"] == 4), 2)
        self.measure_resolution_combo.setCurrentIndex(default_index)
            
        self.measure_resolution_combo.currentIndexChanged.connect(self.on_measure_resolution_changed)
        # add to layout
        slice_layout.addWidget(self.split_measures_button)
        slice_layout.addWidget(self.split_transients_button)
        slice_layout.addWidget(self.measure_resolution_combo)

        # add to layout
        main_layout.addLayout(info_layout)
        main_layout.addLayout(slice_layout)

        # create the slider and label for transient detection
        threshold_layout = QHBoxLayout()

        # Create a label for the slider
        threshold_label = QLabel(config.get_string("labels", "onsetThreshold"))
        threshold_layout.addWidget(threshold_label)

        # Get default threshold from config
        td_config = config.get_setting("audio", "transientDetection", {})
        default_threshold = td_config.get("threshold", 0.2)
        
        # Convert the threshold to slider value (multiply by 100)
        default_slider_value = int(default_threshold * 100)
        
        # Create the slider
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 100)  # Range from 0.01 to 1.00
        self.threshold_slider.setValue(default_slider_value)  # Set from config
        self.threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threshold_slider.setTickInterval(10)
        self.threshold_slider.valueChanged.connect(self.on_threshold_changed)
        threshold_layout.addWidget(self.threshold_slider)

        # Create a label to display the current value
        self.threshold_value_label = QLabel(f"{default_threshold:.2f}")
        threshold_layout.addWidget(self.threshold_value_label)

        # Add the slider layout to your main layout
        main_layout.addLayout(threshold_layout)

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

        # Create buttons
        button_layout = QHBoxLayout()
        self.zoom_in_button = QPushButton(config.get_string("buttons", "zoomIn"))
        self.zoom_out_button = QPushButton(config.get_string("buttons", "zoomOut"))
        self.cut_button = QPushButton(config.get_string("buttons", "cut"))
        
        # Style the cut button to stand out
        self.cut_button.setStyleSheet(f"background-color: {config.get_qt_color('cutButton')}; color: white; font-weight: bold;")
        
        # Connect button signals
        self.zoom_in_button.clicked.connect(self.controller.zoom_in)
        self.zoom_out_button.clicked.connect(self.controller.zoom_out)
        self.cut_button.clicked.connect(self.on_cut_button_clicked)
        
        button_layout.addWidget(self.zoom_in_button)
        button_layout.addWidget(self.zoom_out_button)
        button_layout.addWidget(self.cut_button)
        main_layout.addLayout(button_layout)
        

    def on_plot_click(self, event):
        print("on_plot_click")
        # Allow clicks in either waveform (top or bottom) for stereo display
        if event.inaxes not in [self.ax_left, self.ax_right]:
            return

        modifiers = QApplication.keyboardModifiers()
        print(f"    Modifiers value: {modifiers}")
        print(f"    Is Control: {bool(modifiers & Qt.KeyboardModifier.ControlModifier)}")
        print(f"    Is Shift: {bool(modifiers & Qt.KeyboardModifier.ShiftModifier)}")
        print(f"    Is Alt: {bool(modifiers & Qt.KeyboardModifier.AltModifier)}")
        print(f"    Is Meta: {bool(modifiers & Qt.KeyboardModifier.MetaModifier)}")
        
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
                print(pos_info)
        
        # PRIORITY 1: Check for keyboard modifiers first
        # ==================================================
        
        # Shift+Click to force play the first segment (for easier access)
        # This takes precedence over marker handling to ensure it always works
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            print(f"### Shift+Click detected - forcing first segment playback")
            # Always use a very small value to ensure first segment
            print(f"### Forcing first segment playback (0.01s)")
            self.play_segment.emit(0.01)
            return
            
        # Check for Ctrl+Alt (Option) combination for removing segments
        if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.AltModifier):
            print(f"Ctrl+Alt (Option) combination detected - removing segment at {event.xdata}")
            self.remove_segment.emit(event.xdata)
            return
            
        # Check for Alt+Cmd (Meta) combination for removing segments
        if (modifiers & Qt.KeyboardModifier.AltModifier) and (modifiers & Qt.KeyboardModifier.MetaModifier):
            print(f"Alt+Cmd combination detected - removing segment at {event.xdata}")
            self.remove_segment.emit(event.xdata)
            return
            
        # Add segment with Ctrl+Click
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            print(f"Ctrl detected - adding segment at {event.xdata}")
            self.add_segment.emit(event.xdata)
            return
            
        # Add segment with Alt+Click
        if modifiers & Qt.KeyboardModifier.AltModifier:
            print(f"Alt detected - adding segment at {event.xdata}")
            self.add_segment.emit(event.xdata)
            return
        
        # PRIORITY 2: Check for marker interaction - now with improved marker detection
        # ==================================================
        
        # Check if we're clicking near start marker (with enhanced detection)
        start_marker_x = self.start_marker.get_xdata()[0] if self.start_marker and self.start_marker.get_visible() else None
        print(f"Start marker at: {start_marker_x}")
        
        # Enhanced detection for start marker dragging - higher priority near the edge of waveform
        if start_marker_x is not None and abs(event.xdata - start_marker_x) < 0.1:
            print("Starting to drag start marker (enhanced detection)")
            self.dragging_marker = 'start'
            return
            
        # Check if we're clicking near end marker (with enhanced detection)
        end_marker_x = self.end_marker.get_xdata()[0] if self.end_marker and self.end_marker.get_visible() else None
        print(f"End marker at: {end_marker_x}")
        
        # Enhanced detection for end marker dragging
        if end_marker_x is not None and abs(event.xdata - end_marker_x) < 0.1:
            print("Starting to drag end marker (enhanced detection)")
            self.dragging_marker = 'end'
            return
            
        # Standard marker detection as fallback
        if self.is_near_marker(event.xdata, event.ydata, self.start_marker, self.start_marker_handle):
            print("Starting to drag start marker (standard detection)")
            self.dragging_marker = 'start'
            return
        elif self.is_near_marker(event.xdata, event.ydata, self.end_marker, self.end_marker_handle):
            print("Starting to drag end marker (standard detection)")
            self.dragging_marker = 'end'
            return
                
        # No modifiers - play segment at clicked position
        print(f"### Emitting play_segment signal with click position: {event.xdata}")
        self.play_segment.emit(event.xdata)
            
    def is_near_marker(self, x, y, marker, marker_handle):
        """Check if coordinates are near the marker or its handle"""
        if marker is None or not marker.get_visible():
            print(f"Marker not visible or None")
            return False
        
        marker_x = marker.get_xdata()[0]  # Vertical lines have the same x for all points
        print(f"Checking marker at x={marker_x}")
        
        # Very simple detection for marker:
        # If we're within a reasonable threshold of the marker, count as near
        # This is the original behavior that worked before
        total_time = self.controller.model.total_time
        threshold = total_time * 0.04  # 4% of total duration for hit detection
        
        is_near = abs(x - marker_x) < threshold
        if is_near:
            print(f"Click near marker (within threshold)")
        return is_near

    def on_threshold_changed(self, value):
        threshold = value / 100.0
        self.threshold_value_label.setText(f"{threshold:.2f}")
        self.threshold_changed.emit(threshold)

    def update_slices(self, slices):
        print("Convert slice points to times")
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
        
        print(f"Marker positions before update - start: {start_pos}, end: {end_pos}")
        
        # Validate marker positions against current file boundaries
        if start_pos < 0:
            start_pos = 0
        
        if end_pos > total_time:
            end_pos = total_time
            
        # If end marker is too close to start or exceeds file length, adjust it
        if abs(end_pos - start_pos) < 0.1 or end_pos > total_time:
            print(f"End marker too close to start marker or beyond file end, adjusting: {end_pos} -> {total_time}")
            end_pos = total_time
        
        # Set marker positions
        self.waveform_view.set_start_marker(start_pos)
        self.waveform_view.set_end_marker(end_pos)
        
        # Update the waveform view with slices and total time
        self.waveform_view.update_slices(slice_times, total_time)
        
        # Update controller with marker positions
        self.controller.on_start_marker_changed(start_pos)
        self.controller.on_end_marker_changed(end_pos)
        
        # Store the current slices in the controller
        self.controller.current_slices = slice_times
        print(f"Debugging: Updated current_slices in controller: {self.controller.current_slices}")

    def on_measures_changed(self):
        """Handle changes to the measures input field and update controller"""
        text = self.measures_input.text()
        validator = self.measures_input.validator()
        state, _, _ = validator.validate(text, 0)

        if state == QValidator.State.Acceptable:
            num_measures = int(text)
            print(f"Measure count changed to {num_measures}")
            # Emitting signal will trigger controller.on_measures_changed
            self.measures_changed.emit(num_measures)
        else:
            # Reset to controller's current value or default to 1
            current_measures = getattr(self.controller, 'num_measures', 1)
            self.measures_input.setText(str(current_measures))
            print(f"Invalid measure count, reset to {current_measures}")

    def update_tempo(self, tempo):
        print(f"DEBUG: update_tempo called with tempo={tempo:.2f}")
        self.tempo_display.setText(f"{tempo:.2f} BPM")
        print(f"DEBUG: tempo_display updated to '{tempo:.2f} BPM'")

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
    
    def set_start_marker(self, x_pos):
        """Set the position of the start marker"""
        # Delegate to the waveform view component
        self.waveform_view.set_start_marker(x_pos)
        
    def set_end_marker(self, x_pos):
        """Set the position of the end marker"""
        # Delegate to the waveform view component
        self.waveform_view.set_end_marker(x_pos)
    
    def get_marker_positions(self):
        """Get the positions of both markers, or None if not visible"""
        # Delegate to the waveform view component
        return self.waveform_view.get_marker_positions()
        
    def window_key_press(self, event):
        """Handle Qt key press events for the entire window"""
        print(f"Qt window key press - Key: {event.key()}, Modifiers: {event.modifiers()}")
        
        # Check for spacebar (Qt.Key_Space is 32)
        if event.key() == Qt.Key.Key_Space:
            print("Spacebar press detected! Toggling playback...")
            self.toggle_playback()
            return
        
        # 'r' key handler removed - no longer needed for clearing markers
                
        # Default processing
        super().keyPressEvent(event)
        
    def toggle_playback(self):
        """Toggle playback between start and stop"""
        if self.controller.model.is_playing:
            # If playing, stop playback
            print("Toggle: Stopping playback")
            self.controller.stop_playback()
        else:
            # If not playing, find the most appropriate segment to play
            
            # First, check for markers
            start_pos, end_pos = self.get_marker_positions()
            if start_pos is not None and end_pos is not None:
                # Use markers if both are set
                print(f"Toggle: Playing from markers {start_pos} to {end_pos} with mode: {self.controller.get_playback_mode()}")
                
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
            print(f"Toggle: Emulating click at center of view: {center_pos}")
            self.controller.play_segment(center_pos)
    
    def on_key_press(self, event):
        """Handle key press events"""
        # Print in detail what key was pressed
        print(f"Key pressed: {event.key}")
        print(f"Key modifiers: {QApplication.keyboardModifiers()}")
        
        # Handle spacebar for play/stop toggle
        if event.key == ' ' or event.key == 'space':
            print("Spacebar detected! Toggling playback...")
            self.toggle_playback()
            return
            
        # 'r' key handlers removed - no longer needed for clearing markers
            
        # Allow key presses in either waveform for stereo display
        if event.inaxes not in [self.ax_left, self.ax_right]:
            return
            
        # 'c' key no longer needed for clearing markers
        # Can be repurposed for other functionality
    
    def on_segment_clicked(self, x_position):
        """Handle segment click events from waveform view."""
        print(f"Segment clicked at {x_position:.3f}s")
        self.play_segment.emit(x_position)
        
    def on_marker_dragged(self, marker_type, position):
        """Handle marker drag events from waveform view."""
        print(f"Marker {marker_type} dragged to {position:.3f}s")
        self.dragging_marker = marker_type
        
    def on_marker_released(self, marker_type, position):
        """Handle marker release events from waveform view."""
        print(f"Marker {marker_type} released at {position:.3f}s")
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
                print("Warning: Could not remove existing start marker handle")
                
        self.start_marker_handle = Polygon(empty_triangle, **start_marker_props)
        self.ax.add_patch(self.start_marker_handle)
        print("Created start marker handle (improved visibility)")
        
        # Create the end marker handle (left-pointing triangle)
        if self.end_marker_handle is not None:
            try:
                self.end_marker_handle.remove()
            except:
                print("Warning: Could not remove existing end marker handle")
                
        self.end_marker_handle = Polygon(empty_triangle, **end_marker_props)
        self.ax.add_patch(self.end_marker_handle)
        print("Created end marker handle (improved visibility)")

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
        print(f"Triangle size: height={triangle_height_data}, half-base={triangle_base_half_data}, total_time={total_time}")
        
        if marker_type == 'start':
            marker = self.start_marker
            handle = self.start_marker_handle
            print(f"Updating start marker handle")
        else:  # end marker
            marker = self.end_marker
            handle = self.end_marker_handle
            print(f"Updating end marker handle")
            
        # Ensure marker and handle exist
        if marker is None or handle is None:
            print(f"Marker or handle is None for {marker_type}")
            return
        
        # Force marker to be visible
        if not marker.get_visible():
            print(f"Forcing {marker_type} marker to be visible")
            marker.set_visible(True)
            
        # Get marker position
        marker_x = marker.get_xdata()[0]
        print(f"{marker_type} marker position: {marker_x}")
        
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
        print(f"Updated {marker_type} marker handle: visible={handle.get_visible()}, zorder={handle.get_zorder()}")
    
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

        print(f"Reset markers to file boundaries (0.0s to {total_time:.2f}s)")
    
    def update_plot(self, time, data_left, data_right=None):
        """Update the plot with time and audio data.
        For mono files, data_right can be None or same as data_left.
        For stereo files, data_left and data_right will be different channels.
        """
        # Delegate to the waveform view component
        self.waveform_view.update_plot(time, data_left, data_right)
    
    def _update_marker_visibility(self, ax, start_marker, end_marker):
        """Update marker visibility based on current view
        Note: Markers are now always visible, but we keep this method to make sure
        their triangle handles are updated correctly.
        """
        if start_marker is None or end_marker is None:
            print("Warning: One of the markers is None in _update_marker_visibility")
            return
            
        x_min, x_max = ax.get_xlim()
        
        # Always ensure the marker lines themselves are visible
        if not start_marker.get_visible():
            print("Forcing start marker to be visible")
            start_marker.set_visible(True)
            
        if not end_marker.get_visible():
            print("Forcing end marker to be visible")
            end_marker.set_visible(True)
            
        # Debug marker positions
        start_pos = start_marker.get_xdata()[0]
        end_pos = end_marker.get_xdata()[0]
        print(f"Marker positions - start: {start_pos}, end: {end_pos}")
        
        # Force update triangle handles regardless of view
        if self.start_marker_handle and start_marker == self.start_marker:
            self.start_marker_handle.set_visible(True)
            self._update_marker_handle('start')
            print("Updated start marker handle")
            
        if self.end_marker_handle and end_marker == self.end_marker:
            self.end_marker_handle.set_visible(True)
            self._update_marker_handle('end')
            print("Updated end marker handle")

    def update_scroll_bar(self, visible_time, total_time):
        proportion = visible_time / total_time
        self.scroll_bar.setPageStep(int(proportion * 100))

    def get_scroll_position(self):
        return self.scroll_bar.value()
        
    def highlight_active_segment(self, start_time, end_time):
        """Highlight the currently playing segment"""
        print(f"Highlighting active segment: {start_time:.2f}s to {end_time:.2f}s")
        
        # Store current segment
        self.current_active_segment = (start_time, end_time)
        
        # Delegate to the waveform view component
        self.waveform_view.highlight_active_segment(start_time, end_time)
    
    def clear_active_segment_highlight(self):
        """Remove the active segment highlight"""
        # Delegate to the waveform view component
        self.waveform_view.clear_active_segment_highlight()
        
        # Reset active segment tracking
        self.current_active_segment = (None, None)

    def populate_presets_menu(self, menu):
        """Populate the presets menu with available presets"""
        # Get available presets from controller
        presets = self.controller.get_available_presets()
        
        # Add each preset to the menu
        for preset_id, preset_name in presets:
            action = QAction(preset_name, self)
            # Create a lambda with default arguments to avoid late binding issues
            action.triggered.connect(lambda checked=False, preset=preset_id: self.load_preset(preset))
            menu.addAction(action)
            
    def load_preset(self, preset_id):
        """Load the selected preset"""
        success = self.controller.load_preset(preset_id)
        if not success:
            ErrorHandler.show_error(
                f"Failed to load preset: {preset_id}",
                config.get_string("dialogs", "errorTitle"),
                self
            )
                                
    def update_playback_mode_menu(self, mode):
        """Update the playback mode menu to reflect the current mode
        
        Args:
            mode (str): The current playback mode
        """
        if mode == "one-shot":
            self.one_shot_action.setChecked(True)
        elif mode == "loop":
            self.loop_action.setChecked(True)
        elif mode == "loop-reverse":
            self.loop_reverse_action.setChecked(True)
        else:
            print(f"Warning: Unknown playback mode '{mode}'")
            self.one_shot_action.setChecked(True)
    
    def set_playback_mode(self, mode):
        """Set the playback mode in the controller
        
        Args:
            mode (str): The playback mode to set
        """
        print(f"View set_playback_mode: {mode}")
        if self.controller:
            self.controller.set_playback_mode(mode)
                                
    def on_add_segment(self, position):
        """Handle add_segment signal from waveform view"""
        print(f"RcyView.on_add_segment({position})")
        try:
            self.add_segment.emit(position)
        except Exception as e:
            ErrorHandler.handle_exception(e, context="Adding segment", parent=self)
            
    def on_remove_segment(self, position):
        """Handle remove_segment signal from waveform view"""
        print(f"RcyView.on_remove_segment({position})")
        try:
            self.remove_segment.emit(position)
        except Exception as e:
            ErrorHandler.handle_exception(e, context="Removing segment", parent=self)
    
    def load_session_file(self):
        """Load an existing RCY session file"""
        # Note: This is a placeholder for future implementation
        # For now, just show a message that this feature is coming
        QMessageBox.information(self,
                              "Coming Soon",
                              "Loading session files will be implemented in a future version.\n\n"
                              "Currently, presets are used as sessions.")
    
    def import_audio_file(self):
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

    def on_measure_resolution_changed(self, index):
        # Get the resolution value from the configuration data
        resolution_value = self.measure_resolutions[index]["value"]
        self.controller.set_measure_resolution(resolution_value)
        
    def on_split_measures_clicked(self):
        """Handle the Split by Measures button click by using the current dropdown selection"""
        # Get the current resolution from the dropdown
        current_index = self.measure_resolution_combo.currentIndex()
        resolution_value = self.measure_resolutions[current_index]["value"]
        
        # Trigger the split with the current resolution
        self.controller.split_audio(method='measures', measure_resolution=resolution_value)
        
    def show_keyboard_shortcuts(self):
        """Show a dialog with keyboard shortcuts information"""
        shortcuts_dialog = QDialog(self)
        shortcuts_dialog.setWindowTitle(config.get_string("dialogs", "shortcutsTitle"))
        shortcuts_dialog.setMinimumSize(QSize(500, 400))
        
        # Apply styling to dialog
        shortcuts_dialog.setStyleSheet(f"background-color: {config.get_qt_color('background')}; color: {config.get_qt_color('textColor')};")
        
        layout = QVBoxLayout()
        shortcuts_dialog.setLayout(layout)
        
        # Create text browser for shortcuts
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet(f"background-color: {config.get_qt_color('background')}; color: {config.get_qt_color('textColor')};")
        
        # Set font
        text_browser.setFont(config.get_font('primary'))
        
        # Get marker colors for accurate documentation
        start_marker_color = config.get_qt_color('startMarker')
        end_marker_color = config.get_qt_color('endMarker')
        
        # Prepare HTML content
        shortcuts_html = f"""
        <h2>{config.get_string("dialogs", "shortcutsTitle")}</h2>
        
        <h3>{config.get_string("shortcuts", "markersSection")}</h3>
        <ul>
            <li><b>Click+Drag</b> on marker: {config.get_string("shortcuts", "repositionMarker")}</li>
        </ul>
        
        <h3>{config.get_string("shortcuts", "playbackSection")}</h3>
        <ul>
            <li><b>Click</b> on waveform: {config.get_string("shortcuts", "playSegment")}</li>
            <li><b>Shift+Click</b>: Play first segment (useful if first segment is difficult to click)</li>
            <li><b>Spacebar</b>: Toggle playback (play/stop)</li>
            <li><b>Click</b> again during playback: Stop playback</li>
        </ul>
        
        <h3>{config.get_string("shortcuts", "segmentsSection")}</h3>
        <ul>
            <li><b>Alt+Click</b> or <b>Ctrl+Click</b>: {config.get_string("shortcuts", "addSegment")}</li>
            <li><b>Alt+Cmd+Click</b> (Alt+Meta on macOS) or <b>Ctrl+Alt+Click</b>: {config.get_string("shortcuts", "removeSegment")}</li>
        </ul>
        
        <h3>{config.get_string("shortcuts", "fileOperationsSection")}</h3>
        <ul>
            <li><b>Ctrl+O</b>: {config.get_string("shortcuts", "openFile")}</li>
            <li><b>Ctrl+E</b>: {config.get_string("shortcuts", "exportSegments")}</li>
        </ul>
        """
        
        text_browser.setHtml(shortcuts_html)
        layout.addWidget(text_browser)
        
        # Add close button
        close_button = QPushButton(config.get_string("buttons", "close"))
        close_button.setFont(config.get_font('primary'))
        close_button.clicked.connect(shortcuts_dialog.accept)
        layout.addWidget(close_button)
        
        # Show dialog
        shortcuts_dialog.setModal(True)
        shortcuts_dialog.exec()
        
    def show_about_dialog(self):
        """Show information about the application"""
        # Create custom about dialog to apply styling
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle(config.get_string("dialogs", "aboutTitle"))
        about_dialog.setMinimumSize(QSize(400, 300))
        about_dialog.setStyleSheet(f"background-color: {config.get_qt_color('background')}; color: {config.get_qt_color('textColor')};")
        
        layout = QVBoxLayout()
        about_dialog.setLayout(layout)
        
        # Create text browser for about content
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet(f"background-color: {config.get_qt_color('background')}; color: {config.get_qt_color('textColor')};")
        text_browser.setFont(config.get_font('primary'))
        
        about_html = f"""
        <h1>{config.get_string("about", "title")}</h1>
        <p>{config.get_string("about", "description")}</p>
        <p>{config.get_string("about", "details")}</p>
        <p><a href="{config.get_string("about", "repositoryUrl")}">{config.get_string("about", "repository")}</a></p>
        
        <p>{config.get_string("about", "design")}</p>
        """
        
        text_browser.setHtml(about_html)
        layout.addWidget(text_browser)
        
        # Add close button
        close_button = QPushButton(config.get_string("buttons", "close"))
        close_button.setFont(config.get_font('primary'))
        close_button.clicked.connect(about_dialog.accept)
        layout.addWidget(close_button)
        
        # Show dialog
        about_dialog.setModal(True)
        about_dialog.exec()
