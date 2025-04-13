"""
Simple test script to verify the downsampling functionality
"""
import numpy as np
import time
import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from utils.audio_preview import downsample_waveform, downsample_waveform_max_min, get_downsampled_data

def generate_test_waveform(length=500000):
    """Generate a test waveform with interesting features"""
    t = np.linspace(0, 10, length)
    # Create a signal with multiple frequency components
    signal = np.sin(2 * np.pi * 5 * t) + 0.5 * np.sin(2 * np.pi * 20 * t)
    # Add some spikes to test peak preservation
    for i in range(10):
        idx = np.random.randint(0, length)
        signal[idx] = 2.0 if np.random.random() > 0.5 else -2.0
    return t, signal

def test_performance():
    """Test the performance of different downsampling methods"""
    # Generate a large test waveform
    print("Generating test waveform...")
    t, signal = generate_test_waveform(length=1000000)
    
    # Test simple downsampling
    print("\nTesting simple downsampling...")
    target_lengths = [500, 1000, 2000, 5000, 10000]
    
    for target in target_lengths:
        # Time simple downsampling
        start_time = time.time()
        ds_simple = downsample_waveform(signal, target)
        simple_time = time.time() - start_time
        
        # Time max-min downsampling
        start_time = time.time()
        ds_max_min = downsample_waveform_max_min(signal, target)
        max_min_time = time.time() - start_time
        
        print(f"Target length: {target}")
        print(f"  Simple:   {len(ds_simple)} points in {simple_time:.4f}s")
        print(f"  Max-Min:  {len(ds_max_min)} points in {max_min_time:.4f}s")
        print(f"  Speedup: {max_min_time/simple_time:.2f}x slower")

def plot_comparison_pyqtgraph():
    """Plot a comparison of different downsampling methods using PyQtGraph"""
    app = QApplication(sys.argv)
    
    # Generate a test waveform
    t, signal = generate_test_waveform(length=100000)
    
    # Downsample using different methods
    target_length = 1000
    ds_simple = downsample_waveform(signal, target_length)
    ds_max_min = downsample_waveform_max_min(signal, target_length)
    
    # Create time arrays for plotting
    t_simple = np.linspace(0, 10, len(ds_simple))
    t_max_min = np.linspace(0, 10, len(ds_max_min))
    
    # Create the window
    win = pg.GraphicsLayoutWidget(title="Downsampling Comparison")
    win.resize(1200, 800)
    
    # Original signal (small subset for visibility)
    p1 = win.addPlot(row=0, col=0)
    p1.setTitle(f"Original Signal (showing first 10,000 of {len(signal)} points)")
    p1.plot(t[:10000], signal[:10000], pen='b')
    p1.setLabel('bottom', 'Time', 's')
    p1.setLabel('left', 'Amplitude')
    p1.showGrid(x=True, y=True)
    
    # Simple downsampling
    p2 = win.addPlot(row=1, col=0)
    p2.setTitle(f"Simple Downsampling ({len(ds_simple)} points)")
    p2.plot(t_simple, ds_simple, pen='g')
    p2.setLabel('bottom', 'Time', 's')
    p2.setLabel('left', 'Amplitude')
    p2.showGrid(x=True, y=True)
    
    # Max-min downsampling
    p3 = win.addPlot(row=2, col=0)
    p3.setTitle(f"Max-Min Downsampling ({len(ds_max_min)} points)")
    p3.plot(t_max_min, ds_max_min, pen='r')
    p3.setLabel('bottom', 'Time', 's')
    p3.setLabel('left', 'Amplitude')
    p3.showGrid(x=True, y=True)
    
    # Export image
    exporter = pg.exporters.ImageExporter(win.scene())
    exporter.parameters()['width'] = 1200
    exporter.export("downsampling_comparison.png")
    
    win.show()
    
    # Start event loop
    if (sys.flags.interactive != 1) or not hasattr(pg.QtCore, 'PYQT_VERSION'):
        pg.exec()

if __name__ == "__main__":
    test_performance()
    plot_comparison_pyqtgraph()