from PyQt6.QtWidgets import QLabel, QLineEdit, QComboBox, QMessageBox, QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollBar
from PyQt6.QtGui import QValidator, QIntValidator
from PyQt6.QtCore import Qt, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class RcyView(QMainWindow):
    bars_changed = pyqtSignal(int)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Recycle View")
        self.setGeometry(100, 100, 800, 600)

        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
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
        self.load_button = QPushButton("Load Audio")
        self.load_button.clicked.connect(self.load_audio_file)
        info_layout.addWidget(self.load_button)

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

        # Create plot
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.line, = self.ax.plot([], [])
        self.ax.set_xlabel('')
        self.ax.tick_params(axis='x',
                            which='both',
                            labelbottom=False)
        main_layout.addWidget(self.canvas)
        self.canvas.mpl_connect('button_press_event',
                                self.on_plot_click)

        # Create scroll bar
        self.scroll_bar = QScrollBar(Qt.Orientation.Horizontal)
        self.scroll_bar.valueChanged.connect(self.controller.update_view)
        main_layout.addWidget(self.scroll_bar)

        # Create buttons
        button_layout = QHBoxLayout()
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_in_button.clicked.connect(self.controller.zoom_in)
        self.zoom_out_button.clicked.connect(self.controller.zoom_out)
        button_layout.addWidget(self.zoom_in_button)
        button_layout.addWidget(self.zoom_out_button)
        main_layout.addLayout(button_layout)

    def on_plot_click(self, event):
        print("on_plot_click")
        if event.inaxes == self.ax:
            click_time = event.xdata
            self.controller.handle_plot_click(click_time)


    def update_slices(self, slices):
        print("Convert slice points to times")
        slice_times = [slice_point / self.controller.model.sample_rate for slice_point in slices]
        # Clear previous slice lines
        for line in self.ax.lines[1:]:
            line.remove()
        # Plot new slice lines
        for slice_time in slice_times:
            self.ax.axvline(x=slice_time, color='r', linestyle='--', alpha=0.5)
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

    def update_plot(self, time, data):
        self.line.set_data(time, data)
        self.ax.set_xlim(time[0], time[-1])
        self.ax.set_ylim(min(data), max(data))
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
            "Audio Files (*.wav *.mp3 *.ogg *.flac)")
        if filename:
            self.controller.load_audio_file(filename)
        else:
            QMessageBox.critical(self,
                                 "Error",
                                 "Failed to load audio file.")

    def on_bar_resolution_changed(self, index):
        resolutions = [4, 8, 16]
        self.controller.set_bar_resolution(resolutions[index])
