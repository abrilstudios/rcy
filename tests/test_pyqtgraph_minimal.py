"""
A minimal test program for PyQtGraph waveform view to isolate the segmentation fault.

Run this test from the project root directory with:
PYTHONPATH=./src/python pytest tests/test_pyqtgraph_minimal.py
"""
import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from ui.waveform import create_waveform_view

class MinimalTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQtGraph Waveform Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Create main widget and layout
        self.central_widget = QWidget()
        self.layout = QVBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)
        
        # Create PyQtGraph waveform view
        self.waveform_view = create_waveform_view()
        self.layout.addWidget(self.waveform_view)
        
        # Generate sample data
        samples = 1000
        self.time = np.linspace(0, 4, samples)
        self.data_left = np.sin(2 * np.pi * 1 * self.time) * 0.5
        self.data_right = np.sin(2 * np.pi * 2 * self.time) * 0.5
        
        # Update the plot with sample data
        self.waveform_view.update_plot(self.time, self.data_left, self.data_right)
        
        # Set markers
        self.waveform_view.set_start_marker(1.0)
        self.waveform_view.set_end_marker(3.0)
        
        # Add some slice points
        slices = [0.5, 1.5, 2.5, 3.5]
        self.waveform_view.update_slices(slices, total_time=4.0)
        
        # Highlight a segment
        self.waveform_view.highlight_segment(1.0, 2.0)
        
def main():
    app = QApplication(sys.argv)
    window = MinimalTest()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()