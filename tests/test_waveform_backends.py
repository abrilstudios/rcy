"""
Performance test script for PyQtGraph waveform visualization.
"""
import sys
import numpy as np
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLabel, QRadioButton,
                           QButtonGroup, QGroupBox)
from PyQt6.QtCore import Qt, QTimer

from ui.waveform import create_waveform_view
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


class PerformanceTestWindow(QMainWindow):
    """Window for testing PyQtGraph waveform visualization performance"""
    
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("PyQtGraph Waveform Performance Test")
        self.setGeometry(100, 100, 1200, 600)
        
        # Create benchmark tool
        self.benchmark = BenchmarkTest()
        
        # Create central widget and main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Create waveform panel
        waveform_panel = QVBoxLayout()
        self.waveform_label = QLabel("PyQtGraph Waveform View")
        self.waveform_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        waveform_panel.addWidget(self.waveform_label)
        
        # Create waveform view
        self.waveform_view = create_waveform_view()
        self.waveform_view.segment_clicked.connect(
            lambda pos: self.on_segment_clicked(pos))
        self.waveform_view.marker_dragged.connect(
            lambda marker, pos: self.on_marker_dragged(marker, pos))
        
        waveform_panel.addWidget(self.waveform_view)
        self.performance_info = QLabel("Render time: --")
        self.performance_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        waveform_panel.addWidget(self.performance_info)
        
        # Add panel to the main layout
        main_layout.addLayout(waveform_panel)
        
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
        self.waveform_view.set_start_marker(0)
        self.waveform_view.set_end_marker(self.duration)
    
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
        
        # Time and update the PyQtGraph view
        self.benchmark.start()
        self.waveform_view.update_plot(time_ds, left_ds, right_ds)
        self.waveform_view.total_time = self.duration
        render_time = self.benchmark.stop()
        
        # Update info label
        self.performance_info.setText(f"Render time: {render_time*1000:.1f}ms")
        
        # Update window title
        self.setWindowTitle(f"PyQtGraph Waveform Performance Test - {data_description}")
        
        # Set markers at start and end of waveform whenever we load new data
        self.waveform_view.set_start_marker(0)
        self.waveform_view.set_end_marker(self.duration)
        
        print(f"Loaded {data_description}: {len(time_ds)} samples")
        print(f"  Render time: {render_time*1000:.1f}ms")
    
    def add_slices(self):
        """Add test slices to the waveform view"""
        # Create evenly spaced slices
        slices = np.linspace(0, self.duration, 11)[1:-1]  # Skip first and last
        
        # Add some random variation
        slices += np.random.uniform(-0.2, 0.2, len(slices))
        
        # Time and update the PyQtGraph view
        self.benchmark.start()
        self.waveform_view.update_slices(slices, self.duration)
        render_time = self.benchmark.stop()
        
        # Update info label
        self.performance_info.setText(f"Slice time: {render_time*1000:.1f}ms")
        
        print(f"Added {len(slices)} slices")
        print(f"  Render time: {render_time*1000:.1f}ms")
    
    def set_markers(self):
        """Set test markers on the waveform view"""
        # Set markers at 25% and 75% of the duration
        start_pos = self.duration * 0.25
        end_pos = self.duration * 0.75
        
        # Time and update the PyQtGraph view
        self.benchmark.start()
        self.waveform_view.set_start_marker(start_pos)
        self.waveform_view.set_end_marker(end_pos)
        render_time = self.benchmark.stop()
        
        # Update info label
        self.performance_info.setText(f"Marker time: {render_time*1000:.1f}ms")
        
        print(f"Set markers at {start_pos:.2f}s and {end_pos:.2f}s")
        print(f"  Render time: {render_time*1000:.1f}ms")
    
    def highlight_segment(self):
        """Highlight a segment in the waveform view"""
        # Highlight the middle third
        start_pos = self.duration / 3
        end_pos = self.duration * 2 / 3
        
        # Time and update the PyQtGraph view
        self.benchmark.start()
        self.waveform_view.highlight_active_segment(start_pos, end_pos)
        render_time = self.benchmark.stop()
        
        # Update info label
        self.performance_info.setText(f"Highlight time: {render_time*1000:.1f}ms")
        
        print(f"Highlighted segment from {start_pos:.2f}s to {end_pos:.2f}s")
        print(f"  Render time: {render_time*1000:.1f}ms")
    
    def clear_highlight(self):
        """Clear segment highlight in the waveform view"""
        # Time and update the PyQtGraph view
        self.benchmark.start()
        self.waveform_view.clear_active_segment_highlight()
        render_time = self.benchmark.stop()
        
        # Update info label
        self.performance_info.setText(f"Clear time: {render_time*1000:.1f}ms")
        
        print(f"Cleared highlights")
        print(f"  Render time: {render_time*1000:.1f}ms")
    
    def run_benchmark(self):
        """Run a comprehensive benchmark test"""
        # Reset benchmarks
        self.reset_benchmark()
        
        # Set up test data
        test_samples = [10000, 50000, 100000, 200000, 500000]
        results = []
        
        # Update UI during benchmark
        self.performance_info.setText("Running benchmark...")
        
        # Run benchmarks for each sample size
        for samples in test_samples:
            # Generate data
            t = np.linspace(0, 10, samples)
            left = np.sin(2 * np.pi * t) + 0.1 * np.sin(2 * np.pi * 10 * t)
            right = np.sin(2 * np.pi * t + 0.5) + 0.1 * np.sin(2 * np.pi * 10 * t + 0.5)
            
            # Run 5 iterations for each
            render_times = []
            
            for i in range(5):
                # PyQtGraph test
                self.benchmark.start()
                self.waveform_view.update_plot(t, left, right)
                render_time = self.benchmark.stop()
                render_times.append(render_time)
                
                # Process events to keep UI responsive
                QApplication.processEvents()
            
            # Calculate average
            avg_time = sum(render_times) / len(render_times)
            
            # Store results
            results.append((samples, avg_time))
        
        # Display results
        print("\nBenchmark Results:")
        print("Samples | Render Time (ms)")
        print("---------------------------")
        for samples, render_time in results:
            print(f"{samples:7d} | {render_time*1000:14.2f}")
        
        # Update info label with average results
        avg_render_time = sum(r[1] for r in results) / len(results)
        self.performance_info.setText(f"Benchmark complete - Average render time: {avg_render_time*1000:.2f}ms")
    
    def reset_benchmark(self):
        """Reset benchmark statistics"""
        self.benchmark.reset()
        self.performance_info.setText("Stats reset")
    
    def on_segment_clicked(self, position):
        """Handle segment click events"""
        print(f"Segment clicked at {position:.3f}s")
    
    def on_marker_dragged(self, marker_type, position):
        """Handle marker drag events"""
        print(f"{marker_type} marker dragged to {position:.3f}s")


def main():
    app = QApplication(sys.argv)
    window = PerformanceTestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()