"""
Test script to compare Matplotlib and PyQtGraph waveform visualizations side by side.
This helps evaluate performance and appearance differences between the backends.
"""
import sys
import numpy as np
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLabel, QRadioButton,
                           QButtonGroup, QGroupBox)
from PyQt6.QtCore import Qt, QTimer

from waveform_view import create_waveform_view
from config_manager import config

class BenchmarkTest:
    """Simple benchmark test for measuring performance"""
    def __init__(self):
        self.start_time = 0
        self.times = []
        
    def start(self):
        """Start timing"""
        self.start_time = time.time()
        
    def stop(self):
        """Stop timing and record result"""
        elapsed = time.time() - self.start_time
        self.times.append(elapsed)
        return elapsed
    
    def average(self):
        """Get average time"""
        if not self.times:
            return 0
        return sum(self.times) / len(self.times)
    
    def reset(self):
        """Reset all timings"""
        self.times = []


class ComparisonWindow(QMainWindow):
    """Window for comparing waveform visualization backends"""
    
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("Waveform Backend Comparison")
        self.setGeometry(100, 100, 1400, 800)
        
        # Create benchmark tools
        self.matplotlib_benchmark = BenchmarkTest()
        self.pyqtgraph_benchmark = BenchmarkTest()
        
        # Create central widget and main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Create views layout (side by side)
        views_layout = QHBoxLayout()
        
        # Create left panel (Matplotlib)
        left_panel = QVBoxLayout()
        self.left_label = QLabel("Matplotlib")
        self.left_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(self.left_label)
        
        # Create Matplotlib waveform view
        self.matplotlib_view = create_waveform_view(backend='matplotlib')
        self.matplotlib_view.segment_clicked.connect(
            lambda pos: self.on_segment_clicked('matplotlib', pos))
        self.matplotlib_view.marker_dragged.connect(
            lambda marker, pos: self.on_marker_dragged('matplotlib', marker, pos))
        
        left_panel.addWidget(self.matplotlib_view)
        self.left_info = QLabel("Render time: --")
        self.left_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(self.left_info)
        
        # Create right panel (PyQtGraph)
        right_panel = QVBoxLayout()
        self.right_label = QLabel("PyQtGraph")
        self.right_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_panel.addWidget(self.right_label)
        
        # Create PyQtGraph waveform view
        self.pyqtgraph_view = create_waveform_view(backend='pyqtgraph')
        self.pyqtgraph_view.segment_clicked.connect(
            lambda pos: self.on_segment_clicked('pyqtgraph', pos))
        self.pyqtgraph_view.marker_dragged.connect(
            lambda marker, pos: self.on_marker_dragged('pyqtgraph', marker, pos))
        
        right_panel.addWidget(self.pyqtgraph_view)
        self.right_info = QLabel("Render time: --")
        self.right_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_panel.addWidget(self.right_info)
        
        # Add panels to the views layout
        views_layout.addLayout(left_panel)
        views_layout.addLayout(right_panel)
        
        # Add views layout to main layout
        main_layout.addLayout(views_layout)
        
        # Create test controls
        controls_layout = QHBoxLayout()
        
        # Test data controls
        data_group = QGroupBox("Test Data")
        data_layout = QHBoxLayout()
        
        self.btn_sine = QPushButton("Sine Wave")
        self.btn_sine.clicked.connect(lambda: self.load_test_data('sine'))
        data_layout.addWidget(self.btn_sine)
        
        self.btn_noise = QPushButton("Noise")
        self.btn_noise.clicked.connect(lambda: self.load_test_data('noise'))
        data_layout.addWidget(self.btn_noise)
        
        self.btn_real = QPushButton("Load Real Audio")
        self.btn_real.clicked.connect(lambda: self.load_test_data('real'))
        data_layout.addWidget(self.btn_real)
        
        data_group.setLayout(data_layout)
        controls_layout.addWidget(data_group)
        
        # Test feature controls
        feature_group = QGroupBox("Features")
        feature_layout = QHBoxLayout()
        
        self.btn_slices = QPushButton("Add Slices")
        self.btn_slices.clicked.connect(self.add_slices)
        feature_layout.addWidget(self.btn_slices)
        
        self.btn_markers = QPushButton("Set Markers")
        self.btn_markers.clicked.connect(self.set_markers)
        feature_layout.addWidget(self.btn_markers)
        
        self.btn_highlight = QPushButton("Highlight Segment")
        self.btn_highlight.clicked.connect(self.highlight_segment)
        feature_layout.addWidget(self.btn_highlight)
        
        self.btn_clear = QPushButton("Clear Highlight")
        self.btn_clear.clicked.connect(self.clear_highlight)
        feature_layout.addWidget(self.btn_clear)
        
        feature_group.setLayout(feature_layout)
        controls_layout.addWidget(feature_group)
        
        # Performance test controls
        perf_group = QGroupBox("Performance Tests")
        perf_layout = QHBoxLayout()
        
        self.btn_benchmark = QPushButton("Run Benchmark")
        self.btn_benchmark.clicked.connect(self.run_benchmark)
        perf_layout.addWidget(self.btn_benchmark)
        
        self.btn_reset = QPushButton("Reset Stats")
        self.btn_reset.clicked.connect(self.reset_benchmark)
        perf_layout.addWidget(self.btn_reset)
        
        perf_group.setLayout(perf_layout)
        controls_layout.addWidget(perf_group)
        
        # Add controls layout to main layout
        main_layout.addLayout(controls_layout)
        
        # Set central widget
        self.setCentralWidget(central_widget)
        
        # Initialize properties
        self.duration = 10.0  # seconds
        self.sample_rate = 44100
        self.num_samples = int(self.duration * self.sample_rate)
        self.time = np.linspace(0, self.duration, self.num_samples)
        
        # Load initial data
        self.load_test_data('sine')
        
        # Set initial marker positions at start and end of waveform
        self.matplotlib_view.set_start_marker(0)
        self.matplotlib_view.set_end_marker(self.duration)
        self.pyqtgraph_view.set_start_marker(0)
        self.pyqtgraph_view.set_end_marker(self.duration)
    
    def load_test_data(self, data_type):
        """Load test data for visualization"""
        if data_type == 'sine':
            # Generate a sine wave test signal
            amplitude = 0.5
            frequency = 440  # Hz
            self.data_left = amplitude * np.sin(2 * np.pi * frequency * self.time)
            self.data_left += 0.3 * np.sin(2 * np.pi * frequency * 2 * self.time)
            self.data_left += 0.15 * np.sin(2 * np.pi * frequency * 3 * self.time)
            
            # Create a slightly different right channel
            self.data_right = amplitude * np.sin(2 * np.pi * frequency * self.time + 0.2)
            self.data_right += 0.25 * np.sin(2 * np.pi * frequency * 2 * self.time + 0.1)
            self.data_right += 0.1 * np.sin(2 * np.pi * frequency * 3 * self.time + 0.3)
            
            data_description = "Sine Wave"
            
        elif data_type == 'noise':
            # Generate random noise
            amplitude = 0.5
            self.data_left = amplitude * (2 * np.random.random(self.num_samples) - 1)
            self.data_right = amplitude * (2 * np.random.random(self.num_samples) - 1)
            
            # Add some structure - a few peaks
            peak_positions = np.random.randint(0, self.num_samples, 20)
            for pos in peak_positions:
                if pos + 1000 < self.num_samples:
                    self.data_left[pos:pos+1000] *= 3.0
                    self.data_right[pos:pos+1000] *= 3.0
            
            data_description = "Noise"
            
        elif data_type == 'real':
            # Load actual audio file from audio/amen.wav
            import soundfile as sf
            try:
                audio_data, sample_rate = sf.read('audio/amen.wav', always_2d=True)
                # Adjust sample rate if needed
                self.sample_rate = sample_rate
                self.num_samples = len(audio_data)
                self.duration = self.num_samples / self.sample_rate
                self.time = np.linspace(0, self.duration, self.num_samples)
                
                # Extract channels
                self.data_left = audio_data[:, 0]
                self.data_right = audio_data[:, 1] if audio_data.shape[1] > 1 else audio_data[:, 0]
                
                data_description = "Real Audio"
            except Exception as e:
                print(f"Error loading audio file: {e}")
                # Fall back to sine wave
                self.load_test_data('sine')
                return
        
        # Downsample for display (for better performance)
        target_length = 10000
        if len(self.time) > target_length:
            downsample_factor = max(1, len(self.time) // target_length)
            time_ds = self.time[::downsample_factor]
            left_ds = self.data_left[::downsample_factor]
            right_ds = self.data_right[::downsample_factor]
        else:
            time_ds = self.time
            left_ds = self.data_left
            right_ds = self.data_right
        
        # Time and update the Matplotlib view
        self.matplotlib_benchmark.start()
        self.matplotlib_view.update_plot(time_ds, left_ds, right_ds)
        self.matplotlib_view.total_time = self.duration
        matplotlib_time = self.matplotlib_benchmark.stop()
        
        # Time and update the PyQtGraph view
        self.pyqtgraph_benchmark.start()
        self.pyqtgraph_view.update_plot(time_ds, left_ds, right_ds)
        self.pyqtgraph_view.total_time = self.duration
        pyqtgraph_time = self.pyqtgraph_benchmark.stop()
        
        # Update info labels
        self.left_info.setText(f"Render time: {matplotlib_time*1000:.1f}ms")
        self.right_info.setText(f"Render time: {pyqtgraph_time*1000:.1f}ms")
        
        # Update window title
        self.setWindowTitle(f"Waveform Backend Comparison - {data_description}")
        
        # Set markers at start and end of waveform whenever we load new data
        self.matplotlib_view.set_start_marker(0)
        self.matplotlib_view.set_end_marker(self.duration)
        self.pyqtgraph_view.set_start_marker(0)
        self.pyqtgraph_view.set_end_marker(self.duration)
        
        print(f"Loaded {data_description}: {len(time_ds)} samples")
        print(f"  Matplotlib: {matplotlib_time*1000:.1f}ms")
        print(f"  PyQtGraph: {pyqtgraph_time*1000:.1f}ms")
        print(f"  Speed ratio: {matplotlib_time/pyqtgraph_time:.1f}x")
    
    def add_slices(self):
        """Add test slices to both waveform views"""
        # Create evenly spaced slices
        slices = np.linspace(0, self.duration, 11)[1:-1]  # Skip first and last
        
        # Add some random variation
        slices += np.random.uniform(-0.2, 0.2, len(slices))
        
        # Time and update the Matplotlib view
        self.matplotlib_benchmark.start()
        self.matplotlib_view.update_slices(slices, self.duration)
        matplotlib_time = self.matplotlib_benchmark.stop()
        
        # Time and update the PyQtGraph view
        self.pyqtgraph_benchmark.start()
        self.pyqtgraph_view.update_slices(slices, self.duration)
        pyqtgraph_time = self.pyqtgraph_benchmark.stop()
        
        # Update info labels
        self.left_info.setText(f"Slice time: {matplotlib_time*1000:.1f}ms")
        self.right_info.setText(f"Slice time: {pyqtgraph_time*1000:.1f}ms")
        
        print(f"Added {len(slices)} slices")
        print(f"  Matplotlib: {matplotlib_time*1000:.1f}ms")
        print(f"  PyQtGraph: {pyqtgraph_time*1000:.1f}ms")
        print(f"  Speed ratio: {matplotlib_time/pyqtgraph_time:.1f}x")
    
    def set_markers(self):
        """Set test markers on both waveform views"""
        # Set markers at 25% and 75% of the duration
        start_pos = self.duration * 0.25
        end_pos = self.duration * 0.75
        
        # Time and update the Matplotlib view
        self.matplotlib_benchmark.start()
        self.matplotlib_view.set_start_marker(start_pos)
        self.matplotlib_view.set_end_marker(end_pos)
        matplotlib_time = self.matplotlib_benchmark.stop()
        
        # Time and update the PyQtGraph view
        self.pyqtgraph_benchmark.start()
        self.pyqtgraph_view.set_start_marker(start_pos)
        self.pyqtgraph_view.set_end_marker(end_pos)
        pyqtgraph_time = self.pyqtgraph_benchmark.stop()
        
        # Update info labels
        self.left_info.setText(f"Marker time: {matplotlib_time*1000:.1f}ms")
        self.right_info.setText(f"Marker time: {pyqtgraph_time*1000:.1f}ms")
        
        print(f"Set markers at {start_pos:.2f}s and {end_pos:.2f}s")
        print(f"  Matplotlib: {matplotlib_time*1000:.1f}ms")
        print(f"  PyQtGraph: {pyqtgraph_time*1000:.1f}ms")
        print(f"  Speed ratio: {matplotlib_time/pyqtgraph_time:.1f}x")
    
    def highlight_segment(self):
        """Highlight a segment in both waveform views"""
        # Highlight the middle third
        start_pos = self.duration / 3
        end_pos = self.duration * 2 / 3
        
        # Time and update the Matplotlib view
        self.matplotlib_benchmark.start()
        self.matplotlib_view.highlight_active_segment(start_pos, end_pos)
        matplotlib_time = self.matplotlib_benchmark.stop()
        
        # Time and update the PyQtGraph view
        self.pyqtgraph_benchmark.start()
        self.pyqtgraph_view.highlight_active_segment(start_pos, end_pos)
        pyqtgraph_time = self.pyqtgraph_benchmark.stop()
        
        # Update info labels
        self.left_info.setText(f"Highlight time: {matplotlib_time*1000:.1f}ms")
        self.right_info.setText(f"Highlight time: {pyqtgraph_time*1000:.1f}ms")
        
        print(f"Highlighted segment from {start_pos:.2f}s to {end_pos:.2f}s")
        print(f"  Matplotlib: {matplotlib_time*1000:.1f}ms")
        print(f"  PyQtGraph: {pyqtgraph_time*1000:.1f}ms")
        print(f"  Speed ratio: {matplotlib_time/pyqtgraph_time:.1f}x")
    
    def clear_highlight(self):
        """Clear segment highlight in both waveform views"""
        # Time and update the Matplotlib view
        self.matplotlib_benchmark.start()
        self.matplotlib_view.clear_active_segment_highlight()
        matplotlib_time = self.matplotlib_benchmark.stop()
        
        # Time and update the PyQtGraph view
        self.pyqtgraph_benchmark.start()
        self.pyqtgraph_view.clear_active_segment_highlight()
        pyqtgraph_time = self.pyqtgraph_benchmark.stop()
        
        # Update info labels
        self.left_info.setText(f"Clear time: {matplotlib_time*1000:.1f}ms")
        self.right_info.setText(f"Clear time: {pyqtgraph_time*1000:.1f}ms")
        
        print(f"Cleared highlights")
        print(f"  Matplotlib: {matplotlib_time*1000:.1f}ms")
        print(f"  PyQtGraph: {pyqtgraph_time*1000:.1f}ms")
        print(f"  Speed ratio: {matplotlib_time/pyqtgraph_time:.1f}x")
    
    def run_benchmark(self):
        """Run a comprehensive benchmark test"""
        # Reset benchmarks
        self.reset_benchmark()
        
        # Set up test data
        test_samples = [10000, 50000, 100000, 200000, 500000]
        results = []
        
        # Update UI during benchmark
        self.left_info.setText("Running benchmark...")
        self.right_info.setText("Running benchmark...")
        
        # Run benchmarks for each sample size
        for samples in test_samples:
            # Generate data
            t = np.linspace(0, 10, samples)
            left = np.sin(2 * np.pi * t) + 0.1 * np.sin(2 * np.pi * 10 * t)
            right = np.sin(2 * np.pi * t + 0.5) + 0.1 * np.sin(2 * np.pi * 10 * t + 0.5)
            
            # Run 5 iterations for each
            matplotlib_times = []
            pyqtgraph_times = []
            
            for i in range(5):
                # Matplotlib test
                self.matplotlib_benchmark.start()
                self.matplotlib_view.update_plot(t, left, right)
                matplotlib_time = self.matplotlib_benchmark.stop()
                matplotlib_times.append(matplotlib_time)
                
                # PyQtGraph test
                self.pyqtgraph_benchmark.start()
                self.pyqtgraph_view.update_plot(t, left, right)
                pyqtgraph_time = self.pyqtgraph_benchmark.stop()
                pyqtgraph_times.append(pyqtgraph_time)
                
                # Process events to keep UI responsive
                QApplication.processEvents()
            
            # Calculate averages
            matplotlib_avg = sum(matplotlib_times) / len(matplotlib_times)
            pyqtgraph_avg = sum(pyqtgraph_times) / len(pyqtgraph_times)
            speed_ratio = matplotlib_avg / pyqtgraph_avg
            
            # Store results
            results.append((samples, matplotlib_avg, pyqtgraph_avg, speed_ratio))
        
        # Display results
        print("\nBenchmark Results:")
        print("Samples | Matplotlib (ms) | PyQtGraph (ms) | Ratio")
        print("------------------------------------------------")
        for samples, matplotlib_time, pyqtgraph_time, ratio in results:
            print(f"{samples:7d} | {matplotlib_time*1000:14.2f} | {pyqtgraph_time*1000:13.2f} | {ratio:5.1f}x")
        
        # Update info labels with average results
        total_ratio = sum(r[3] for r in results) / len(results)
        self.left_info.setText(f"Benchmark complete - Average: {total_ratio:.1f}x slower than PyQtGraph")
        self.right_info.setText(f"Benchmark complete - Average: {total_ratio:.1f}x faster than Matplotlib")
    
    def reset_benchmark(self):
        """Reset benchmark statistics"""
        self.matplotlib_benchmark.reset()
        self.pyqtgraph_benchmark.reset()
        self.left_info.setText("Stats reset")
        self.right_info.setText("Stats reset")
    
    def on_segment_clicked(self, backend, position):
        """Handle segment click events"""
        print(f"{backend.capitalize()} segment clicked at {position:.3f}s")
    
    def on_marker_dragged(self, backend, marker_type, position):
        """Handle marker drag events"""
        print(f"{backend.capitalize()} {marker_type} marker dragged to {position:.3f}s")


def main():
    app = QApplication(sys.argv)
    window = ComparisonWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()