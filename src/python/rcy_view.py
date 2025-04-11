from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QComboBox, QMessageBox, QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollBar, QSlider, QDialog, QTextBrowser
from PyQt6.QtGui import QAction, QValidator, QIntValidator, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from config_manager import config
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
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

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu(config.get_string("menus", "file"))

        # Open action
        open_action = QAction(config.get_string("menus", "open"), self)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Open an audio file')
        open_action.triggered.connect(self.load_audio_file)
        file_menu.addAction(open_action)
        
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

    def export_segments(self):
        directory = QFileDialog.getExistingDirectory(self,
                                                     config.get_string("dialogs", "exportDirectoryTitle"))
        if directory:
            self.controller.export_segments(directory)

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

        # Create the slider
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 100)  # Range from 0.01 to 1.00
        self.threshold_slider.setValue(10)  # Default value 0.10
        self.threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threshold_slider.setTickInterval(10)
        self.threshold_slider.valueChanged.connect(self.on_threshold_changed)
        threshold_layout.addWidget(self.threshold_slider)

        # Create a label to display the current value
        self.threshold_value_label = QLabel("0.10")
        threshold_layout.addWidget(self.threshold_value_label)

        # Add the slider layout to your main layout
        main_layout.addLayout(threshold_layout)

        # Create plot
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.figure.patch.set_facecolor(config.get_qt_color('background'))
        self.canvas = FigureCanvas(self.figure)
        # Enable focus on the canvas for keyboard events
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Make the canvas focus when clicked
        self.canvas.setFocus()
        
        # Flag for stereo display settings
        self.stereo_display = self._get_audio_config("stereoDisplay", True)
        
        # Setup for either mono or stereo display
        if self.stereo_display:
            # Create two subplots for stereo
            self.ax_left = self.figure.add_subplot(211)  # Top subplot for left channel
            self.ax_right = self.figure.add_subplot(212)  # Bottom subplot for right channel
            
            # Configure left channel plot
            self.ax_left.set_facecolor(config.get_qt_color('background'))
            self.line_left, = self.ax_left.plot([], [], color=config.get_qt_color('waveform'), linewidth=1)
            self.ax_left.set_xlabel('')
            # Remove L/R labels as requested
            self.ax_left.tick_params(axis='x', which='both', labelbottom=False)
            self.ax_left.grid(False)
            self.ax_left.tick_params(colors=config.get_qt_color('gridLines'))
            
            # Configure right channel plot
            self.ax_right.set_facecolor(config.get_qt_color('background'))
            self.line_right, = self.ax_right.plot([], [], color=config.get_qt_color('waveform'), linewidth=1)
            self.ax_right.set_xlabel('')
            # Remove L/R labels as requested
            self.ax_right.tick_params(axis='x', which='both', labelbottom=False)
            self.ax_right.grid(False)
            self.ax_right.tick_params(colors=config.get_qt_color('gridLines'))
            
            # Initialize markers as hidden - on both subplots
            self.start_marker_left = self.ax_left.axvline(x=0, color=config.get_qt_color('startMarker'), 
                                                        linestyle='-', linewidth=1, alpha=0.8, visible=False)
            self.end_marker_left = self.ax_left.axvline(x=0, color=config.get_qt_color('endMarker'), 
                                                      linestyle='-', linewidth=1, alpha=0.8, visible=False)
            
            self.start_marker_right = self.ax_right.axvline(x=0, color=config.get_qt_color('startMarker'), 
                                                          linestyle='-', linewidth=1, alpha=0.8, visible=False)
            self.end_marker_right = self.ax_right.axvline(x=0, color=config.get_qt_color('endMarker'), 
                                                        linestyle='-', linewidth=1, alpha=0.8, visible=False)
            
            # Use ax_left as the primary subplot for event handling
            self.ax = self.ax_left
            self.start_marker = self.start_marker_left
            self.end_marker = self.end_marker_left
            
            # Adjust spacing between subplots
            self.figure.subplots_adjust(hspace=0.1)
        else:
            # Single subplot for mono display (original behavior)
            self.ax = self.figure.add_subplot(111)
            self.ax.set_facecolor(config.get_qt_color('background'))
            self.line, = self.ax.plot([], [], color=config.get_qt_color('waveform'), linewidth=1)
            self.ax.set_xlabel('')
            self.ax.tick_params(axis='x', which='both', labelbottom=False)
            self.ax.grid(False)
            self.ax.tick_params(colors=config.get_qt_color('gridLines'))
            
            # Initialize markers as hidden - using same width (1) as segment markers for consistency
            self.start_marker = self.ax.axvline(x=0, color=config.get_qt_color('startMarker'), 
                                              linestyle='-', linewidth=1, alpha=0.8, visible=False)
            self.end_marker = self.ax.axvline(x=0, color=config.get_qt_color('endMarker'), 
                                            linestyle='-', linewidth=1, alpha=0.8, visible=False)
            
            # For mono compatibility
            self.ax_left = self.ax
            self.ax_right = None
            self.line_left = self.line
            self.line_right = None
            self.start_marker_left = self.start_marker
            self.end_marker_left = self.end_marker
            self.start_marker_right = None
            self.end_marker_right = None
        
        # Initialize triangle handles (they'll be created properly when markers are shown)
        self.start_marker_handle = None
        self.end_marker_handle = None
        
        # Initialize triangle handles with empty data
        self._create_marker_handles()
        
        main_layout.addWidget(self.canvas)
        # Connect all event handlers and store the connection IDs for debugging
        self.cid_press = self.canvas.mpl_connect('button_press_event', self.on_plot_click)
        self.cid_release = self.canvas.mpl_connect('button_release_event', self.on_button_release)
        self.cid_motion = self.canvas.mpl_connect('motion_notify_event', self.on_motion_notify)
        self.cid_key = self.canvas.mpl_connect('key_press_event', self.on_key_press)
        
        # Print connection IDs to verify they're working
        print(f"Event connections: press={self.cid_press}, release={self.cid_release}, motion={self.cid_motion}, key={self.cid_key}")

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
        
    def _get_audio_config(self, key, default_value):
        """Helper method to get audio configuration from config manager"""
        try:
            return config.get_value_from_json_file("audio.json", key, default_value)
        except:
            return default_value

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
            if hasattr(self.controller, 'current_slices') and self.controller.current_slices:
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
            
        # Check for Alt+Cmd (Meta) combination for removing segments
        if (modifiers & Qt.KeyboardModifier.AltModifier) and (modifiers & Qt.KeyboardModifier.MetaModifier):
            print(f"Alt+Cmd combination detected - removing segment at {event.xdata}")
            self.remove_segment.emit(event.xdata)
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
        
        # Save marker states - always keep markers visible
        start_visible = True
        end_visible = True
        
        # Get current marker positions or use default values
        start_pos = self.start_marker.get_xdata()[0] if hasattr(self.start_marker, 'get_xdata') and self.start_marker else 0
        end_pos = self.end_marker.get_xdata()[0] if hasattr(self.end_marker, 'get_xdata') and self.end_marker else self.controller.model.total_time
        
        print(f"Marker positions before update - start: {start_pos}, end: {end_pos}")
        
        # If end marker is too close to start, adjust it
        if abs(end_pos - start_pos) < 0.1:
            print(f"End marker too close to start marker, adjusting: {end_pos} -> {self.controller.model.total_time}")
            end_pos = self.controller.model.total_time
            
        if self.stereo_display:
            # Clear previous lines except the main waveform plot lines in both subplots
            for line in self.ax_left.lines[1:]:
                line.remove()
            for line in self.ax_right.lines[1:]:
                line.remove()
                
            # Re-add our markers with consistent width to both subplots - always visible
            self.start_marker_left = self.ax_left.axvline(x=start_pos, color=config.get_qt_color('startMarker'), 
                                                        linestyle='-', linewidth=2, alpha=0.8, visible=True)
            self.end_marker_left = self.ax_left.axvline(x=end_pos, color=config.get_qt_color('endMarker'), 
                                                      linestyle='-', linewidth=2, alpha=0.8, visible=True)
            
            self.start_marker_right = self.ax_right.axvline(x=start_pos, color=config.get_qt_color('startMarker'), 
                                                          linestyle='-', linewidth=2, alpha=0.8, visible=True)
            self.end_marker_right = self.ax_right.axvline(x=end_pos, color=config.get_qt_color('endMarker'), 
                                                        linestyle='-', linewidth=2, alpha=0.8, visible=True)
            
            # Plot new slice lines on both subplots
            for slice_time in slice_times:
                self.ax_left.axvline(x=slice_time, color=config.get_qt_color('sliceActive'), linestyle='--', alpha=0.5)
                self.ax_right.axvline(x=slice_time, color=config.get_qt_color('sliceActive'), linestyle='--', alpha=0.5)
            
            # Update references for event handling
            self.start_marker = self.start_marker_left
            self.end_marker = self.end_marker_left
            
            # Debug visualization
            print(f"Created start_marker at {start_pos} (visible: {self.start_marker.get_visible()})")
            print(f"Created end_marker at {end_pos} (visible: {self.end_marker.get_visible()})")
        else:
            # Clear previous lines except the main waveform plot line
            for line in self.ax.lines[1:]:
                line.remove()
                
            # Re-add our markers with consistent width - always visible
            self.start_marker = self.ax.axvline(x=start_pos, color=config.get_qt_color('startMarker'), 
                                              linestyle='-', linewidth=2, alpha=0.8, visible=True)
            self.end_marker = self.ax.axvline(x=end_pos, color=config.get_qt_color('endMarker'), 
                                            linestyle='-', linewidth=2, alpha=0.8, visible=True)
            
            # Update references for mono compatibility
            self.start_marker_left = self.start_marker
            self.end_marker_left = self.end_marker
            
            # Debug visualization
            print(f"Created start_marker at {start_pos} (visible: {self.start_marker.get_visible()})")
            print(f"Created end_marker at {end_pos} (visible: {self.end_marker.get_visible()})")
            
            # Plot new slice lines
            for slice_time in slice_times:
                self.ax.axvline(x=slice_time, color=config.get_qt_color('sliceActive'), linestyle='--', alpha=0.5)
        
        # Recreate the triangle handles
        self._create_marker_handles()
        
        # Always update both marker handles
        self._update_marker_handle('start')
        self._update_marker_handle('end')
        
        # Update controller with marker positions
        if hasattr(self.controller, 'on_start_marker_changed'):
            self.controller.on_start_marker_changed(start_pos)
        if hasattr(self.controller, 'on_end_marker_changed'):
            self.controller.on_end_marker_changed(end_pos)
            
        self.canvas.draw()
        
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
        self.tempo_display.setText(f"{tempo:.2f} BPM")

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
        # Ensure start marker is within the audio bounds
        # For direct setting, we don't clamp to current view limits
        
        # Snap to start of waveform if within threshold
        if x_pos < self.snap_threshold:
            print(f"Snapped start marker to 0.0s (was at {x_pos:.3f}s)")
            x_pos = 0.0
        
        # If end marker exists, ensure start marker is before it
        if self.end_marker.get_visible():
            end_x = self.end_marker.get_xdata()[0]
            x_pos = min(x_pos, end_x - 0.01)  # Keep a small gap
        
        # Update the marker in primary subplot
        self.start_marker.set_xdata([x_pos, x_pos])
        self.start_marker.set_visible(True)
        
        # If in stereo mode, also update the second marker
        if self.stereo_display and self.start_marker_right is not None:
            self.start_marker_right.set_xdata([x_pos, x_pos])
            self.start_marker_right.set_visible(True)
        
        # Update the triangle handle
        self._update_marker_handle('start')
        
        self.canvas.draw()
        
    def set_end_marker(self, x_pos):
        """Set the position of the end marker"""
        # Ensure end marker is within the audio bounds
        # For direct setting, we don't clamp to current view limits
        
        # Get total audio duration for end boundary snapping
        total_time = self.controller.model.total_time
        
        # Snap to end of waveform if within threshold
        if total_time - x_pos < self.snap_threshold:
            print(f"Snapped end marker to {total_time:.3f}s (was at {x_pos:.3f}s)")
            x_pos = total_time
        
        # If start marker exists, ensure end marker is after it
        if self.start_marker.get_visible():
            start_x = self.start_marker.get_xdata()[0]
            x_pos = max(x_pos, start_x + 0.01)  # Keep a small gap
        
        # Update the marker in primary subplot
        self.end_marker.set_xdata([x_pos, x_pos])
        self.end_marker.set_visible(True)
        
        # If in stereo mode, also update the second marker
        if self.stereo_display and self.end_marker_right is not None:
            self.end_marker_right.set_xdata([x_pos, x_pos])
            self.end_marker_right.set_visible(True)
        
        # Update the triangle handle
        self._update_marker_handle('end')
        
        self.canvas.draw()
    
    def get_marker_positions(self):
        """Get the positions of both markers, or None if not visible"""
        start_pos = self.start_marker.get_xdata()[0] if self.start_marker.get_visible() else None
        end_pos = self.end_marker.get_xdata()[0] if self.end_marker.get_visible() else None
        return start_pos, end_pos
        
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
                print(f"Toggle: Playing from markers {start_pos} to {end_pos}")
                self.controller.model.play_segment(start_pos, end_pos)
                return
                
            # If no markers, find the segment that would be clicked
            # We'll use the center of the current view as the "virtual click" position
            x_min, x_max = self.ax.get_xlim()
            center_pos = (x_min + x_max) / 2
            
            # Emulate a click at the center of the current view
            print(f"Toggle: Emulating click at center of view: {center_pos}")
            self.controller.play_segment(center_pos)
    
    def on_key_press(self, event):
        """Handle matplotlib key press events"""
        # Print in detail what key was pressed
        print(f"Matplotlib key pressed: {event.key}")
        print(f"Matplotlib key modifiers: {QApplication.keyboardModifiers()}")
        
        # Handle spacebar for play/stop toggle
        if event.key == ' ' or event.key == 'space':
            print("Spacebar detected in matplotlib handler! Toggling playback...")
            self.toggle_playback()
            return
            
        # 'r' key handlers removed - no longer needed for clearing markers
            
        # Allow key presses in either waveform for stereo display
        if event.inaxes not in [self.ax_left, self.ax_right]:
            return
            
        # 'c' key no longer needed for clearing markers
        # Can be repurposed for other functionality
            
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
        
        # Briefly highlight the selection in both waveforms if in stereo mode
        if self.stereo_display:
            # Highlight in both waveforms
            selection_left = self.ax_left.axvspan(start_pos, end_pos, color=config.get_qt_color('selectionHighlight'), alpha=0.3, zorder=10)
            selection_right = self.ax_right.axvspan(start_pos, end_pos, color=config.get_qt_color('selectionHighlight'), alpha=0.3, zorder=10)
            selection_areas = [selection_left, selection_right]
        else:
            # Just highlight in the single waveform for mono
            selection_area = self.ax.axvspan(start_pos, end_pos, color=config.get_qt_color('selectionHighlight'), alpha=0.3, zorder=10)
            selection_areas = [selection_area]
            
        self.canvas.draw()
            
        # Confirm the action
        reply = QMessageBox.question(self,
                                    config.get_string("dialogs", "confirmCutTitle"),
                                    config.get_string("dialogs", "confirmCutMessage"),
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        # Remove highlight from all areas
        for area in selection_areas:
            area.remove()
        self.canvas.draw()
                                    
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
        # Get file duration
        if hasattr(self.controller.model, 'total_time'):
            total_time = self.controller.model.total_time
            
            # Reset start marker to beginning of file
            self.set_start_marker(0.0)
            
            # Reset end marker to end of file
            self.set_end_marker(total_time)
            
            # Let controller know about the reset
            if hasattr(self.controller, 'on_start_marker_changed'):
                self.controller.on_start_marker_changed(0.0)
            if hasattr(self.controller, 'on_end_marker_changed'):
                self.controller.on_end_marker_changed(total_time)
                
            print(f"Reset markers to file boundaries (0.0s to {total_time:.2f}s)")
        else:
            print("Cannot reset markers: file duration unknown")
            
        self.canvas.draw()
    
    def update_plot(self, time, data_left, data_right=None):
        """Update the plot with time and audio data.
        For mono files, data_right can be None or same as data_left.
        For stereo files, data_left and data_right will be different channels.
        """
        if self.stereo_display and data_right is not None:
            # Stereo display - update both channels
            self.line_left.set_data(time, data_left)
            self.line_right.set_data(time, data_right)
            
            # Set identical x limits for both subplots
            self.ax_left.set_xlim(time[0], time[-1])
            self.ax_right.set_xlim(time[0], time[-1])
            
            # Set y limits based on each channel's min/max
            self.ax_left.set_ylim(min(data_left), max(data_left))
            self.ax_right.set_ylim(min(data_right), max(data_right))
            
            # Update markers on both plots
            self._update_marker_visibility(self.ax_left, self.start_marker_left, self.end_marker_left)
            self._update_marker_visibility(self.ax_right, self.start_marker_right, self.end_marker_right)
        else:
            # Mono display - update single plot
            self.line_left.set_data(time, data_left)
            self.ax_left.set_xlim(time[0], time[-1])
            self.ax_left.set_ylim(min(data_left), max(data_left))
            
            # Update markers
            self._update_marker_visibility(self.ax_left, self.start_marker_left, self.end_marker_left)
        
        # Update the triangle handles if needed
        if self.start_marker.get_visible() and self.start_marker_handle:
            self._update_marker_handle('start')
            
        if self.end_marker.get_visible() and self.end_marker_handle:
            self._update_marker_handle('end')
            
        self.canvas.draw()
    
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
        start_pos = start_marker.get_xdata()[0] if hasattr(start_marker, 'get_xdata') else "unknown"
        end_pos = end_marker.get_xdata()[0] if hasattr(end_marker, 'get_xdata') else "unknown"
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
            QMessageBox.critical(self,
                                config.get_string("dialogs", "errorTitle"),
                                f"Failed to load preset: {preset_id}")
    
    def load_audio_file(self):
        filename, _ = QFileDialog.getOpenFileName(self,
            config.get_string("dialogs", "openFileTitle"),
            "",
            config.get_string("dialogs", "audioFileFilter"))
        if filename:
            self.controller.load_audio_file(filename)
        else:
            QMessageBox.critical(self,
                                 config.get_string("dialogs", "errorTitle"),
                                 config.get_string("dialogs", "errorLoadingFile"))

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
            <li><b>Alt+Click</b>: {config.get_string("shortcuts", "addSegment")}</li>
            <li><b>Alt+Cmd+Click</b> (Alt+Meta on macOS): {config.get_string("shortcuts", "removeSegment")}</li>
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
