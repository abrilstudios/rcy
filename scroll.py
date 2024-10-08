import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollBar
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class RecycleView(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Recycle View")
        self.setGeometry(100, 100, 800, 600)

        # Set time parameters
        self.total_time = 100  # Total time range in seconds
        self.visible_time = 10  # Visible time window in seconds
        self.sample_rate = 100  # Samples per second

        # Generate full sine wave data
        self.time = np.linspace(0,
                                self.total_time,
                                self.total_time * self.sample_rate)
        self.data = np.sin(2 * np.pi * self.time)

        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Create plot widget and layout
        plot_widget = QWidget()
        plot_layout = QVBoxLayout()
        plot_widget.setLayout(plot_layout)

        # Create Matplotlib figure and canvas
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        plot_layout.addWidget(self.canvas)

        # Create horizontal scroll bar
        self.scroll_bar = QScrollBar(Qt.Orientation.Horizontal)
        self.update_scroll_bar()
        self.scroll_bar.valueChanged.connect(self.update_plot)
        plot_layout.addWidget(self.scroll_bar)

        # Add plot widget to main layout
        main_layout.addWidget(plot_widget)

        # create button layout and add buttons
        button_layout = QVBoxLayout()
        zoom_buttons_layout = QHBoxLayout()
        self.zoom_in_button = QPushButton("+")
        self.zoom_out_button = QPushButton("-")
        zoom_buttons_layout.addWidget(self.zoom_in_button)
        zoom_buttons_layout.addWidget(self.zoom_out_button)
        self.click_me_button = QPushButton("click")
        button_layout.addLayout(zoom_buttons_layout)
        button_layout.addWidget(self.click_me_button)
        main_layout.addLayout(button_layout)
        # connect buttons to actions
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button.clicked.connect(self.zoom_out)

        # Initialize plot
        self.plot_data()

    def plot_data(self):
        self.ax = self.figure.add_subplot(111)
        initial_data = self.data[:int(self.visible_time * self.sample_rate)]
        initial_time = self.time[:int(self.visible_time * self.sample_rate)]
        self.line, = self.ax.plot(initial_time, initial_data)
        self.ax.set_xlim(0, self.visible_time)
        self.ax.set_ylim(-1.1, 1.1)
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Amplitude')
        self.canvas.draw()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scroll_bar()

    def update_plot(self, value):
        total_samples = len(self.time)
        visible_samples = int(self.visible_time * self.sample_rate)
    
        # Ensure visible_samples doesn't exceed total_samples
        visible_samples = min(visible_samples, total_samples)
    
        # Calculate start_sample based on scroll bar value
        if self.scroll_bar.maximum() > 0:
            start_sample = int(value * (total_samples - visible_samples) / self.scroll_bar.maximum())
        else:
            start_sample = 0
    
        end_sample = min(start_sample + visible_samples, total_samples)
    
        # Adjust start_sample if end_sample hit the upper bound
        start_sample = max(0, end_sample - visible_samples)
    
        visible_time = self.time[start_sample:end_sample]
        visible_data = self.data[start_sample:end_sample]
    
        if len(visible_time) > 0 and len(visible_data) > 0:
            self.line.set_data(visible_time, visible_data)
            self.ax.set_xlim(visible_time[0], visible_time[-1])
            self.canvas.draw()
        else:
            print("Warning: No data to display")

    def zoom_in(self):
        self.visible_time *= 0.95 
        self.update_scroll_bar()
        self.update_plot(self.scroll_bar.value())

    def zoom_out(self):
        self.visible_time = min(self.visible_time * 1.05, self.total_time)
        self.update_scroll_bar()
        self.update_plot(self.scroll_bar.value())

    def update_zoom(self):
        # Ensure visible_time stays within reasonable bounds
        self.visible_time = max(1, min(self.visible_time, self.total_time))
        # Update scroll bar
        self.update_scroll_bar()
        current_value = self.scroll_bar.value()
        max_value = (self.total_time - self.visible_time) * self.sample_rate
        self.scroll_bar.setRange(0, int(max_value))
        self.scroll_bar.setValue(min(current_value, int(max_value)))
        # Update plot
        self.update_plot(self.scroll_bar.value())

    def update_scroll_bar(self):
        total_samples = len(self.time)
        visible_samples = int(self.visible_time * self.sample_rate)
    
        # Calculate the proportion of visible samples
        proportion = visible_samples / total_samples
    
        # Set the range to be the total number of samples minus visible samples
        max_value = max(1, total_samples - visible_samples)
        self.scroll_bar.setRange(0, max_value)
    
        # Set the page step to be the proportion of the scroll bar's range
        #page_step = int(proportion * (max_value + visible_samples))
        page_step = max(1, int(proportion * total_samples))
        self.scroll_bar.setPageStep(page_step)
    
        # Set the single step to be 1% of the visible samples
        self.scroll_bar.setSingleStep(max(1, int(visible_samples * 0.01)))
    
        # Ensure the current value is within the new range
        current_value = min(self.scroll_bar.value(), max_value)
        self.scroll_bar.setValue(current_value)
    
        print(f"Visible: {visible_samples}/{total_samples}, Page Step: {page_step}, Range: 0-{max_value}")  # Debug print

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RecycleView()
    window.show()
    sys.exit(app.exec())
