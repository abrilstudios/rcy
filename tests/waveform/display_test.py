#!/usr/bin/env python
"""
Manual test for waveform visualization.
This script creates a window with waveform visualization for interactive testing.

Usage:
    python -m tests.waveform.display_test [matplotlib|pyqtgraph]
"""
import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout


def main():
    """Main function to create and show the waveform test window"""
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] in ['matplotlib', 'pyqtgraph']:
        backend = sys.argv[1]
    else:
        backend = 'pyqtgraph'  # Default to PyQtGraph
    
    print(f"Using {backend} backend for waveform visualization")
    
    # Create application
    app = QApplication([])
    
    # Import waveform_view module
    try:
        from waveform_view import create_waveform_view
    except ImportError:
        print("Error: waveform_view module not found. Run this script with PYTHONPATH set to include src/python")
        sys.exit(1)
    
    # Create main window
    win = QMainWindow()
    win.setWindowTitle(f"Waveform Visualization Test ({backend})")
    win.resize(800, 600)
    
    # Create central widget with layout
    central_widget = QWidget()
    main_layout = QVBoxLayout(central_widget)
    win.setCentralWidget(central_widget)
    
    # Create PyQtGraph waveform view
    waveform_view = create_waveform_view(backend=backend)
    main_layout.addWidget(waveform_view)
    
    # Generate sample data
    samples = 1000
    time = np.linspace(0, 4, samples)
    data_left = np.sin(2 * np.pi * 1 * time) * 0.5
    data_right = np.sin(2 * np.pi * 2 * time) * 0.5
    
    # Update the plot with sample data
    waveform_view.update_plot(time, data_left, data_right)
    
    # Create button layout
    button_layout = QHBoxLayout()
    main_layout.addLayout(button_layout)
    
    # Add buttons for common operations
    def add_button(text, callback):
        """Helper to add a button to the layout"""
        button = QPushButton(text)
        button.clicked.connect(callback)
        button_layout.addWidget(button)
        return button
    
    # Button to set markers
    add_button("Set Markers", lambda: (
        waveform_view.set_start_marker(1.0),
        waveform_view.set_end_marker(3.0)
    ))
    
    # Button to add slice points
    add_button("Add Slices", lambda: 
        waveform_view.update_slices([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5], total_time=4.0)
    )
    
    # Button to highlight a segment
    add_button("Highlight 1.0-2.0", lambda: 
        waveform_view.highlight_segment(1.0, 2.0)
    )
    
    # Button to clear highlights
    add_button("Clear Highlight", lambda: 
        waveform_view.clear_segment_highlight()
    )
    
    # Button to generate random data
    def generate_random_data():
        """Generate random waveform data"""
        samples = 1000
        time = np.linspace(0, 4, samples)
        # Create more complex waveform with multiple frequencies
        t = np.linspace(0, 4, samples)
        data_left = (
            0.5 * np.sin(2 * np.pi * 1 * t) + 
            0.3 * np.sin(2 * np.pi * 2 * t) +
            0.2 * np.sin(2 * np.pi * 3 * t)
        )
        data_right = (
            0.5 * np.sin(2 * np.pi * 1.5 * t) + 
            0.3 * np.sin(2 * np.pi * 2.5 * t) +
            0.2 * np.sin(2 * np.pi * 3.5 * t)
        )
        waveform_view.update_plot(time, data_left, data_right)
    
    add_button("Random Data", generate_random_data)
    
    # Show window and start event loop
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()