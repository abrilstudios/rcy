from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QComboBox, QMessageBox, QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollBar, QSlider, QDialog, QTextBrowser
from PyQt6.QtGui import QAction, QValidator, QIntValidator, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from config_manager import config
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

class RcyView(QMainWindow):
    bars_changed = pyqtSignal(int)
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
        self.dragging_marker = None
        self.init_ui()
        self.create_menu_bar()
        
        # Set key press handler for the entire window
        self.keyPressEvent = self.window_key_press

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        # Open action
        open_action = QAction('Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Open an audio file')
        open_action.triggered.connect(self.load_audio_file)
        file_menu.addAction(open_action)

        # Export action
        export_action = QAction('Export', self)
        export_action.setShortcut('Ctrl+E')
        export_action.setStatusTip('Export segments and SFZ file')
        export_action.triggered.connect(self.export_segments)
        file_menu.addAction(export_action)

        # Save As action
        save_as_action = QAction('Save As', self)
        save_as_action.triggered.connect(self.save_as)
        file_menu.addAction(save_as_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        # Keyboard shortcuts action
        shortcuts_action = QAction('Keyboard Shortcuts', self)
        shortcuts_action.triggered.connect(self.show_keyboard_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        # About action
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def export_segments(self):
        directory = QFileDialog.getExistingDirectory(self,
                                                     "Select Export Directory")
        if directory:
            self.controller.export_segments(directory)

    def save_as(self):
        # Implement save as functionality
        pass

    def init_ui(self):
        self.setWindowTitle("Recycle View")
        self.setGeometry(100, 100, 800, 600)

        # Set application-wide font
        app = QApplication.instance()
        if app:
            app.setFont(config.get_font('primary'))

        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Set background color
        main_widget.setStyleSheet(f"background-color: {config.get_qt_color('background')};")
        
        self.setCentralWidget(main_widget)

        # create top bar info row
        info_layout = QHBoxLayout()
        slice_layout = QHBoxLayout()

        ## Number of Bars Input
        self.bars_label = QLabel("Number of bars:")
        self.bars_input = QLineEdit("1")
        self.bars_input.setValidator(QIntValidator(1, 1000))
        self.bars_input.editingFinished.connect(self.on_bars_changed)
        info_layout.addWidget(self.bars_label)
        info_layout.addWidget(self.bars_input)

        ## Tempo Display
        self.tempo_label = QLabel("Tempo:")
        self.tempo_display = QLineEdit("N/A")
        self.tempo_display.setReadOnly(True)
        info_layout.addWidget(self.tempo_label)
        info_layout.addWidget(self.tempo_display)

        ## Load Button
        #self.load_button = QPushButton("Load Audio")
        #self.load_button.clicked.connect(self.load_audio_file)
        #info_layout.addWidget(self.load_button)

        ## add split buttons
        self.split_bars_button = QPushButton("Split by Bars")
        self.split_bars_button.clicked.connect(lambda: self.controller.split_audio('bars'))

        self.split_transients_button = QPushButton("Split by Transients")
        self.split_transients_button.clicked.connect(lambda: self.controller.split_audio('transients'))

        # Add bar resolution dropdown
        self.bar_resolution_combo = QComboBox()
        self.bar_resolution_combo.addItems(["4th notes", "8th notes", "16th notes"])
        self.bar_resolution_combo.currentIndexChanged.connect(self.on_bar_resolution_changed)
        # add to layout
        slice_layout.addWidget(self.split_bars_button)
        slice_layout.addWidget(self.split_transients_button)
        slice_layout.addWidget(self.bar_resolution_combo)

        # add to layout
        main_layout.addLayout(info_layout)
        main_layout.addLayout(slice_layout)

        # create the slider and label for transient detection
        threshold_layout = QHBoxLayout()

        # Create a label for the slider
        threshold_label = QLabel("Onset Threshold:")
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
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(config.get_qt_color('background'))
        self.line, = self.ax.plot([], [], color=config.get_qt_color('waveform'), linewidth=1)
        self.ax.set_xlabel('')
        self.ax.tick_params(axis='x',
                            which='both',
                            labelbottom=False)
        
        # Set grid color if grid is shown
        self.ax.grid(False)  # Turn off grid by default
        self.ax.tick_params(colors=config.get_qt_color('gridLines'))
        
        # Initialize markers as hidden - using same width (1) as segment markers for consistency
        self.start_marker = self.ax.axvline(x=0, color=config.get_qt_color('startMarker'), linestyle='-', linewidth=1, alpha=0.8, visible=False)
        self.end_marker = self.ax.axvline(x=0, color=config.get_qt_color('endMarker'), linestyle='-', linewidth=1, alpha=0.8, visible=False)
        
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
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_out_button = QPushButton("Zoom Out")
        self.cut_button = QPushButton("Cut Selection")
        
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
        if event.inaxes != self.ax:
            return

        modifiers = QApplication.keyboardModifiers()
        print(f"    Modifiers value: {modifiers}")
        print(f"    Is Control: {bool(modifiers & Qt.KeyboardModifier.ControlModifier)}")
        print(f"    Is Shift: {bool(modifiers & Qt.KeyboardModifier.ShiftModifier)}")
        print(f"    Is Alt: {bool(modifiers & Qt.KeyboardModifier.AltModifier)}")
        print(f"    Is Meta: {bool(modifiers & Qt.KeyboardModifier.MetaModifier)}")
        
        # Check if we're clicking near a marker
        if self.is_near_marker(event.xdata, self.start_marker):
            self.dragging_marker = 'start'
            return
        elif self.is_near_marker(event.xdata, self.end_marker):
            self.dragging_marker = 'end'
            return
            
        # Handle other clicks with modifiers
        # On macOS, Command (Meta) key is sometimes triggered when Control is pressed
        # Check for end marker setting first with more options
        if (modifiers & Qt.KeyboardModifier.ControlModifier) or (modifiers & Qt.KeyboardModifier.MetaModifier):
            # Check if it's actually the "Control" key using the event.modifiers string representation
            print(f"Raw modifiers string: {str(modifiers)}")
            # For macOS, we'll treat both Control and Command as candidates for end marker
            # Add a special key specifically for end marker: 'e'
            self.set_end_marker(event.xdata)
            print(f"Set end marker at {event.xdata}")
            return
            
        # Other modifiers
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Set start marker with Shift+Click
            self.set_start_marker(event.xdata)
            print(f"Set start marker at {event.xdata}")
        elif modifiers & Qt.KeyboardModifier.AltModifier:
            # Original Alt functionality
            self.add_segment.emit(event.xdata)
        else:
            # No modifiers
            self.play_segment.emit(event.xdata)
            
    def is_near_marker(self, x, marker):
        """Check if x coordinate is near the given marker"""
        if not marker.get_visible():
            return False
        
        marker_x = marker.get_xdata()[0]  # Vertical lines have the same x for all points
        # Define "near" as within 5% of the view width for easier grabbing
        # This creates a wider hit area without changing the visual width
        view_width = self.ax.get_xlim()[1] - self.ax.get_xlim()[0]
        threshold = view_width * 0.05  # Increased from 2% to 5% for better usability
        
        return abs(x - marker_x) < threshold

    def on_threshold_changed(self, value):
        threshold = value / 100.0
        self.threshold_value_label.setText(f"{threshold:.2f}")
        self.threshold_changed.emit(threshold)

    def update_slices(self, slices):
        print("Convert slice points to times")
        slice_times = [slice_point / self.controller.model.sample_rate for slice_point in slices]
        
        # Save marker states
        start_visible = self.start_marker.get_visible()
        end_visible = self.end_marker.get_visible()
        start_pos = self.start_marker.get_xdata()[0] if start_visible else 0
        end_pos = self.end_marker.get_xdata()[0] if end_visible else 0
        
        # Clear previous lines except the main waveform plot line
        for line in self.ax.lines[1:]:
            line.remove()
            
        # Re-add our markers with consistent width
        self.start_marker = self.ax.axvline(x=start_pos, color=config.get_qt_color('startMarker'), linestyle='-', linewidth=1, alpha=0.8, visible=start_visible)
        self.end_marker = self.ax.axvline(x=end_pos, color=config.get_qt_color('endMarker'), linestyle='-', linewidth=1, alpha=0.8, visible=end_visible)
        
        # Plot new slice lines
        for slice_time in slice_times:
            self.ax.axvline(x=slice_time, color=config.get_qt_color('sliceActive'), linestyle='--', alpha=0.5)
        
        self.canvas.draw()
        
        # Store the current slices in the controller
        self.controller.current_slices = slice_times
        print(f"Debugging: Updated current_slices in controller: {self.controller.current_slices}")

    def on_bars_changed(self):
        text = self.bars_input.text()
        validator = self.bars_input.validator()
        state, _, _ = validator.validate(text, 0)

        if state == QValidator.State.Acceptable:
            num_bars = int(text)
            self.bars_changed.emit(num_bars)
        else:
            self.bars_input.setText(str(getattr(self.controller,
                                                'num_bars', 1)))

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
        if not self.dragging_marker or event.inaxes != self.ax:
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
        x_min, x_max = self.ax.get_xlim()
        x_pos = max(x_min, min(x_max, x_pos))
        
        # If end marker exists, ensure start marker is before it
        if self.end_marker.get_visible():
            end_x = self.end_marker.get_xdata()[0]
            x_pos = min(x_pos, end_x - 0.01)  # Keep a small gap
        
        self.start_marker.set_xdata([x_pos, x_pos])
        self.start_marker.set_visible(True)
        self.canvas.draw()
        
    def set_end_marker(self, x_pos):
        """Set the position of the end marker"""
        # Ensure end marker is within the audio bounds
        x_min, x_max = self.ax.get_xlim()
        x_pos = max(x_min, min(x_max, x_pos))
        
        # If start marker exists, ensure end marker is after it
        if self.start_marker.get_visible():
            start_x = self.start_marker.get_xdata()[0]
            x_pos = max(x_pos, start_x + 0.01)  # Keep a small gap
        
        self.end_marker.set_xdata([x_pos, x_pos])
        self.end_marker.set_visible(True)
        self.canvas.draw()
    
    def get_marker_positions(self):
        """Get the positions of both markers, or None if not visible"""
        start_pos = self.start_marker.get_xdata()[0] if self.start_marker.get_visible() else None
        end_pos = self.end_marker.get_xdata()[0] if self.end_marker.get_visible() else None
        return start_pos, end_pos
        
    def window_key_press(self, event):
        """Handle Qt key press events for the entire window"""
        print(f"Qt window key press - Key: {event.key()}, Modifiers: {event.modifiers()}")
        
        # Check for 'r' key (Qt.Key_R is 82)
        if event.key() == Qt.Key.Key_R:
            print("'r' key detected in window handler")
            
            # Check for Ctrl modifier (ControlModifier is 67108864 in Qt)
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                print("Ctrl+R detected! Clearing markers...")
                self.clear_markers()
                return
                
        # Default processing
        super().keyPressEvent(event)
    
    def on_key_press(self, event):
        """Handle matplotlib key press events"""
        # Print in detail what key was pressed
        print(f"Matplotlib key pressed: {event.key}")
        print(f"Matplotlib key modifiers: {QApplication.keyboardModifiers()}")
        
        # Add a simple 'r' key handler as an immediate solution
        if event.key == 'r':
            self.clear_markers()
            print("Cleared markers via 'r' key")
            return
            
        # Try other variations for debugging
        if event.key in ['ctrl+r', 'control+r', 'r+ctrl', 'r+control']:
            self.clear_markers()
            print("Cleared markers via Ctrl+R")
            return
            
        # If no active plot, ignore other keys
        if event.inaxes != self.ax:
            return
            
        # Use 'c' key to clear markers (legacy)
        if event.key == 'c':
            # 'c' key clears markers
            self.clear_markers()
            print("Cleared markers via 'c' key")
            
    def on_cut_button_clicked(self):
        """Handle the Cut button click"""
        # Get marker positions
        start_pos, end_pos = self.get_marker_positions()
        
        # Check if both markers are set
        if start_pos is None or end_pos is None:
            QMessageBox.warning(self, 
                                "Cannot Cut", 
                                "Both start and end markers must be set to cut the audio.\n\n"
                                "Use Shift+Click to set the start marker and Ctrl+Click to set the end marker.")
            return
        
        # Briefly highlight the selection
        selection_area = self.ax.axvspan(start_pos, end_pos, color=config.get_qt_color('selectionHighlight'), alpha=0.3, zorder=10)
        self.canvas.draw()
            
        # Confirm the action
        reply = QMessageBox.question(self,
                                    "Confirm Cut",
                                    f"Are you sure you want to trim the audio to the selected region?\n\n"
                                    f"This will remove all audio outside the markers and reset all slices.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        # Remove highlight
        selection_area.remove()
        self.canvas.draw()
                                    
        if reply == QMessageBox.StandardButton.Yes:
            # Emit the signal to request cutting
            self.cut_requested.emit(start_pos, end_pos)
            
            # Clear the markers after cutting
            self.clear_markers()
    
    def clear_markers(self):
        """Hide both markers"""
        self.start_marker.set_visible(False)
        self.end_marker.set_visible(False)
        self.canvas.draw()
    
    def update_plot(self, time, data):
        self.line.set_data(time, data)
        self.ax.set_xlim(time[0], time[-1])
        self.ax.set_ylim(min(data), max(data))
        
        # Update marker visibility based on current view
        x_min, x_max = self.ax.get_xlim()
        
        if self.start_marker.get_visible():
            start_x = self.start_marker.get_xdata()[0]
            # If start marker is outside current view, hide it
            if start_x < x_min or start_x > x_max:
                self.start_marker.set_visible(False)
                
        if self.end_marker.get_visible():
            end_x = self.end_marker.get_xdata()[0]
            # If end marker is outside current view, hide it
            if end_x < x_min or end_x > x_max:
                self.end_marker.set_visible(False)
        
        self.canvas.draw()

    def update_scroll_bar(self, visible_time, total_time):
        proportion = visible_time / total_time
        self.scroll_bar.setPageStep(int(proportion * 100))

    def get_scroll_position(self):
        return self.scroll_bar.value()

    def load_audio_file(self):
        filename, _ = QFileDialog.getOpenFileName(self,
            "Open audio file",
            "",
            "Audio Files (*.wav *.mp3 *.ogg *.flac *.aif *.aiff)")
        if filename:
            self.controller.load_audio_file(filename)
        else:
            QMessageBox.critical(self,
                                 "Error",
                                 "Failed to load audio file.")

    def on_bar_resolution_changed(self, index):
        resolutions = [4, 8, 16]
        self.controller.set_bar_resolution(resolutions[index])
        
    def show_keyboard_shortcuts(self):
        """Show a dialog with keyboard shortcuts information"""
        shortcuts_dialog = QDialog(self)
        shortcuts_dialog.setWindowTitle("Keyboard Shortcuts")
        shortcuts_dialog.setMinimumSize(QSize(500, 400))
        
        # Apply styling to dialog
        shortcuts_dialog.setStyleSheet(f"background-color: {config.get_qt_color('background')};")
        
        layout = QVBoxLayout()
        shortcuts_dialog.setLayout(layout)
        
        # Create text browser for shortcuts
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet(f"background-color: {config.get_qt_color('background')};")
        
        # Set font
        text_browser.setFont(config.get_font('primary'))
        
        # Get marker colors for accurate documentation
        start_marker_color = config.get_qt_color('startMarker')
        end_marker_color = config.get_qt_color('endMarker')
        
        # Prepare HTML content
        shortcuts_html = f"""
        <h2>Keyboard Shortcuts</h2>
        
        <h3>Markers</h3>
        <ul>
            <li><b>Shift+Click</b>: Set start marker (<span style="color: {start_marker_color};">blue</span> vertical line)</li>
            <li><b>Ctrl+Click</b>: Set end marker (<span style="color: {end_marker_color};">blue</span> vertical line)</li>
            <li><b>r</b>: Clear both markers</li>
            <li><b>Click+Drag</b> on marker: Reposition marker</li>
        </ul>
        
        <h3>Playback</h3>
        <ul>
            <li><b>Click</b> on waveform: Play segment at click position</li>
        </ul>
        
        <h3>Segments</h3>
        <ul>
            <li><b>Alt+Click</b>: Add segment at click position</li>
            <li><b>Meta+Click</b> (Command on macOS): Remove segment nearest to click</li>
        </ul>
        
        <h3>File Operations</h3>
        <ul>
            <li><b>Ctrl+O</b>: Open audio file</li>
            <li><b>Ctrl+E</b>: Export segments and SFZ file</li>
        </ul>
        """
        
        text_browser.setHtml(shortcuts_html)
        layout.addWidget(text_browser)
        
        # Add close button
        close_button = QPushButton("Close")
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
        about_dialog.setWindowTitle("About RCY")
        about_dialog.setMinimumSize(QSize(400, 300))
        about_dialog.setStyleSheet(f"background-color: {config.get_qt_color('background')};")
        
        layout = QVBoxLayout()
        about_dialog.setLayout(layout)
        
        # Create text browser for about content
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet(f"background-color: {config.get_qt_color('background')};")
        text_browser.setFont(config.get_font('primary'))
        
        about_html = f"""
        <h1>RCY</h1>
        <p>An audio slicing and SFZ export tool for sample-based music production.</p>
        <p>RCY lets you load breakbeat loops, slice them automatically or manually, 
        and export them as SFZ files for use in samplers like TAL-Sampler.</p>
        <p><a href="https://github.com/tnn1t1s/rcy">GitHub Repository</a></p>
        
        <p>Designed with a color palette inspired by New Order's Movement, 
        brutalist design, and hauntological software.</p>
        """
        
        text_browser.setHtml(about_html)
        layout.addWidget(text_browser)
        
        # Add close button
        close_button = QPushButton("Close")
        close_button.setFont(config.get_font('primary'))
        close_button.clicked.connect(about_dialog.accept)
        layout.addWidget(close_button)
        
        # Show dialog
        about_dialog.setModal(True)
        about_dialog.exec()
