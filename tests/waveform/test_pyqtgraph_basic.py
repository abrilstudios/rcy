"""
Basic test for PyQtGraph waveform visualization.
This test creates a simple waveform display using PyQtGraph to verify it works correctly.
"""
import sys
import pytest
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget


@pytest.fixture
def app():
    """PyQt application fixture"""
    app = QApplication([])
    yield app


@pytest.fixture
def waveform_view(app):
    """Create a waveform view fixture with PyQtGraph backend"""
    from waveform_view import create_waveform_view
    
    # Create a test window
    win = QMainWindow()
    win.setWindowTitle("PyQtGraph Waveform Test")
    win.resize(800, 600)
    
    # Create central widget with layout
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    win.setCentralWidget(central_widget)
    
    # Create PyQtGraph waveform view
    waveform_view = create_waveform_view()
    layout.addWidget(waveform_view)
    
    # Generate sample data
    samples = 1000
    time = np.linspace(0, 4, samples)
    data_left = np.sin(2 * np.pi * 1 * time) * 0.5
    data_right = np.sin(2 * np.pi * 2 * time) * 0.5
    
    # Update the plot with sample data
    waveform_view.update_plot(time, data_left, data_right)
    
    # Set markers
    waveform_view.set_start_marker(1.0)
    waveform_view.set_end_marker(3.0)
    
    # Add some slice points
    slices = [0.5, 1.5, 2.5, 3.5]
    waveform_view.update_slices(slices, total_time=4.0)
    
    # Highlight a segment
    waveform_view.highlight_segment(1.0, 2.0)
    
    # Show window only if requested for manual inspection (not during automated testing)
    win.show_if_interactive = lambda: win.show()
    
    yield waveform_view
    
    # Clean up
    win.close()


def test_waveform_creation(waveform_view):
    """Test that waveform view can be created"""
    assert waveform_view is not None


def test_marker_positions(waveform_view):
    """Test marker positions are set correctly"""
    start_pos, end_pos = waveform_view.get_marker_positions()
    assert start_pos == 1.0
    assert end_pos == 3.0


if __name__ == "__main__":
    # If run directly, show the window
    app = QApplication([])
    from waveform_view import create_waveform_view
    
    # Create main window
    win = QMainWindow()
    win.setWindowTitle("PyQtGraph Waveform Test")
    win.resize(800, 600)
    
    # Create central widget with layout
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    win.setCentralWidget(central_widget)
    
    # Create PyQtGraph waveform view
    waveform_view = create_waveform_view()
    layout.addWidget(waveform_view)
    
    # Generate sample data
    samples = 1000
    time = np.linspace(0, 4, samples)
    data_left = np.sin(2 * np.pi * 1 * time) * 0.5
    data_right = np.sin(2 * np.pi * 2 * time) * 0.5
    
    # Update the plot with sample data
    waveform_view.update_plot(time, data_left, data_right)
    
    # Set markers
    waveform_view.set_start_marker(1.0)
    waveform_view.set_end_marker(3.0)
    
    # Add some slice points
    slices = [0.5, 1.5, 2.5, 3.5]
    waveform_view.update_slices(slices, total_time=4.0)
    
    # Highlight a segment
    waveform_view.highlight_segment(1.0, 2.0)
    
    # Show window and start event loop
    win.show()
    sys.exit(app.exec())