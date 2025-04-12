"""
Test script for the PyQtGraph-based waveform visualization widget.
This script creates a simple application to test the WaveformView widget.
"""
import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QWidget
from PyQt6.QtCore import Qt
from pyqtgraph_waveform import WaveformView

class TestWindow(QMainWindow):
    """Test window for PyQtGraph waveform view"""
    
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("PyQtGraph Waveform Test")
        self.setGeometry(100, 100, 1200, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Create waveform view
        self.waveform_view = WaveformView()
        main_layout.addWidget(self.waveform_view)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Add test buttons
        self.btn_load_sine = QPushButton("Load Sine Wave")
        self.btn_load_sine.clicked.connect(self.load_sine_wave)
        button_layout.addWidget(self.btn_load_sine)
        
        self.btn_load_noise = QPushButton("Load Noise")
        self.btn_load_noise.clicked.connect(self.load_noise)
        button_layout.addWidget(self.btn_load_noise)
        
        self.btn_add_slices = QPushButton("Add Slices")
        self.btn_add_slices.clicked.connect(self.add_slices)
        button_layout.addWidget(self.btn_add_slices)
        
        self.btn_set_markers = QPushButton("Set Markers")
        self.btn_set_markers.clicked.connect(self.set_markers)
        button_layout.addWidget(self.btn_set_markers)
        
        # Add button layout to main layout
        main_layout.addLayout(button_layout)
        
        # Set central widget
        self.setCentralWidget(central_widget)
        
        # Connect signals from waveform view
        self.waveform_view.marker_dragged.connect(self.on_marker_dragged)
        self.waveform_view.segment_clicked.connect(self.on_segment_clicked)
        
        # Generate initial data
        self.duration = 10.0  # seconds
        self.sample_rate = 44100
        self.num_samples = int(self.duration * self.sample_rate)
        self.time = np.linspace(0, self.duration, self.num_samples)
        
        # Load initial sine wave
        self.load_sine_wave()
    
    def load_sine_wave(self):
        """Load a sine wave test signal"""
        # Generate a simple sine wave
        frequency = 440  # Hz
        amplitude = 0.5
        self.data_left = amplitude * np.sin(2 * np.pi * frequency * self.time)
        
        # Add some harmonics for a more complex wave
        self.data_left += 0.3 * np.sin(2 * np.pi * frequency * 2 * self.time)
        self.data_left += 0.15 * np.sin(2 * np.pi * frequency * 3 * self.time)
        
        # Create a slightly different right channel
        self.data_right = amplitude * np.sin(2 * np.pi * frequency * self.time + 0.2)
        self.data_right += 0.25 * np.sin(2 * np.pi * frequency * 2 * self.time + 0.1)
        self.data_right += 0.1 * np.sin(2 * np.pi * frequency * 3 * self.time + 0.3)
        
        # Downsample for display (for better performance)
        downsample_factor = 20
        time_ds = self.time[::downsample_factor]
        left_ds = self.data_left[::downsample_factor]
        right_ds = self.data_right[::downsample_factor]
        
        # Update the waveform view
        self.waveform_view.update_plot(time_ds, left_ds, right_ds)
        self.waveform_view.total_time = self.duration
        
        print(f"Loaded sine wave: {len(time_ds)} samples")
    
    def load_noise(self):
        """Load a noise test signal"""
        # Generate random noise
        amplitude = 0.5
        self.data_left = amplitude * (2 * np.random.random(self.num_samples) - 1)
        self.data_right = amplitude * (2 * np.random.random(self.num_samples) - 1)
        
        # Add some structure - a few peaks
        peak_positions = np.random.randint(0, self.num_samples, 20)
        for pos in peak_positions:
            self.data_left[pos:pos+1000] *= 3.0
            self.data_right[pos:pos+1000] *= 3.0
        
        # Downsample for display
        downsample_factor = 20
        time_ds = self.time[::downsample_factor]
        left_ds = self.data_left[::downsample_factor]
        right_ds = self.data_right[::downsample_factor]
        
        # Update the waveform view
        self.waveform_view.update_plot(time_ds, left_ds, right_ds)
        self.waveform_view.total_time = self.duration
        
        print(f"Loaded noise: {len(time_ds)} samples")
    
    def add_slices(self):
        """Add test slices to the waveform"""
        # Create evenly spaced slices
        slices = np.linspace(0, self.duration, 11)[1:-1]  # Skip first and last
        
        # Add some random variation
        slices += np.random.uniform(-0.2, 0.2, len(slices))
        
        # Update the waveform view
        self.waveform_view.update_slices(slices, self.duration)
        
        print(f"Added slices at: {slices}")
    
    def set_markers(self):
        """Set test markers on the waveform"""
        # Set markers at 25% and 75% of the duration
        start_pos = self.duration * 0.25
        end_pos = self.duration * 0.75
        
        # Update the waveform view
        self.waveform_view.set_start_marker(start_pos)
        self.waveform_view.set_end_marker(end_pos)
        
        print(f"Set markers at {start_pos}s and {end_pos}s")
    
    def on_marker_dragged(self, marker_type, position):
        """Handle marker drag events"""
        print(f"Marker '{marker_type}' dragged to {position:.3f}s")
    
    def on_segment_clicked(self, position):
        """Handle segment click events"""
        print(f"Segment clicked at {position:.3f}s")


def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()