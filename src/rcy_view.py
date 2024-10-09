from PyQt6.QtWidgets import QLabel, QLineEdit, QMessageBox, QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollBar
from PyQt6.QtGui import QIntValidator
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class RcyView(QMainWindow):
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

        ## Number of Bars Input
        self.bars_label = QLabel("Number of bars:")
        self.bars_input = QLineEdit("1")
        self.bars_input.setValidator(QIntValidator(1, 1000))
        self.bars_input.textChanged.connect(self.on_bars_changed)
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

        main_layout.addLayout(info_layout)

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

    def on_bars_changed(self, text):
        if text:
            self.controller.set_num_bars(int(text))

    def update_tempo(self):
        tempo = self.controller.get_tempo()
        if tempo is not None:
            self.tempo_display.setText(f"{tempo:.2f} BPM")
        else:
            self.tempo_display.setText("N/A")

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
