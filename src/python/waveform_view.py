"""
Abstract waveform visualization interface that can use different rendering backends.
This module provides a factory for creating waveform views with either Matplotlib or PyQtGraph.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPen, QBrush
from config_manager import config
import matplotlib
matplotlib.use('Qt5Agg')  # Use Qt5Agg backend for matplotlib
import pyqtgraph as pg


class BaseWaveformView(QWidget):
    """Base class for waveform visualization"""
    # Define signals
    marker_dragged = pyqtSignal(str, float)   # (marker_type, position)
    segment_clicked = pyqtSignal(float)       # (x_position)
    marker_released = pyqtSignal(str, float)  # (marker_type, position)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dragging_marker = None
        self.current_slices = []
        self.total_time = 0
        self.snap_threshold = config.get_ui_setting("markerSnapping", "snapThreshold", 0.025)
        self.stereo_display = config.get_value_from_json_file("audio.json", "stereoDisplay", True)
    
    def update_plot(self, time, data_left, data_right=None):
        """Update the plot with new audio data"""
        raise NotImplementedError("Subclasses must implement update_plot")
    
    def update_slices(self, slices, total_time=None):
        """Update the segment slices displayed on the waveform"""
        raise NotImplementedError("Subclasses must implement update_slices")
    
    def set_start_marker(self, position):
        """Set the position of the start marker"""
        raise NotImplementedError("Subclasses must implement set_start_marker")
    
    def set_end_marker(self, position):
        """Set the position of the end marker"""
        raise NotImplementedError("Subclasses must implement set_end_marker")
    
    def get_marker_positions(self):
        """Get the positions of both markers"""
        raise NotImplementedError("Subclasses must implement get_marker_positions")
    
    # Highlight and clear highlight methods are intentionally removed from the interface


class MatplotlibWaveformView(BaseWaveformView):
    """Matplotlib implementation of the waveform visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Import matplotlib components
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        from matplotlib.lines import Line2D
        from matplotlib.patches import Polygon
        
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create figure and canvas
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.figure.patch.set_facecolor(config.get_qt_color('background'))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.canvas.setFocus()
        
        # Setup for either mono or stereo display
        if self.stereo_display:
            # Create two subplots for stereo
            self.ax_left = self.figure.add_subplot(211)
            self.ax_right = self.figure.add_subplot(212)
            
            # Configure left channel plot
            self.ax_left.set_facecolor(config.get_qt_color('background'))
            self.line_left, = self.ax_left.plot([], [], color=config.get_qt_color('waveform'), linewidth=1)
            self.ax_left.set_xlabel('')
            self.ax_left.tick_params(axis='x', which='both', labelbottom=False)
            self.ax_left.grid(False)
            self.ax_left.tick_params(colors=config.get_qt_color('gridLines'))
            
            # Configure right channel plot
            self.ax_right.set_facecolor(config.get_qt_color('background'))
            self.line_right, = self.ax_right.plot([], [], color=config.get_qt_color('waveform'), linewidth=1)
            self.ax_right.set_xlabel('')
            self.ax_right.tick_params(axis='x', which='both', labelbottom=False)
            self.ax_right.grid(False)
            self.ax_right.tick_params(colors=config.get_qt_color('gridLines'))
            
            # Initialize markers as hidden
            self.start_marker_left = self.ax_left.axvline(x=0, color=config.get_qt_color('startMarker'), 
                                                      linestyle='-', linewidth=1, alpha=0.8, visible=False)
            self.end_marker_left = self.ax_left.axvline(x=0, color=config.get_qt_color('endMarker'), 
                                                    linestyle='-', linewidth=1, alpha=0.8, visible=False)
            
            self.start_marker_right = self.ax_right.axvline(x=0, color=config.get_qt_color('startMarker'), 
                                                        linestyle='-', linewidth=1, alpha=0.8, visible=False)
            self.end_marker_right = self.ax_right.axvline(x=0, color=config.get_qt_color('endMarker'), 
                                                      linestyle='-', linewidth=1, alpha=0.8, visible=False)
            
            # Use ax_left as the primary subplot for event handling
            self.ax = self.ax_left
            self.start_marker = self.start_marker_left
            self.end_marker = self.end_marker_left
            
            # Adjust spacing between subplots
            self.figure.subplots_adjust(hspace=0.1)
        else:
            # Single subplot for mono display
            self.ax = self.figure.add_subplot(111)
            self.ax.set_facecolor(config.get_qt_color('background'))
            self.line, = self.ax.plot([], [], color=config.get_qt_color('waveform'), linewidth=1)
            self.ax.set_xlabel('')
            self.ax.tick_params(axis='x', which='both', labelbottom=False)
            self.ax.grid(False)
            self.ax.tick_params(colors=config.get_qt_color('gridLines'))
            
            # Initialize markers as hidden
            self.start_marker = self.ax.axvline(x=0, color=config.get_qt_color('startMarker'), 
                                            linestyle='-', linewidth=1, alpha=0.8, visible=False)
            self.end_marker = self.ax.axvline(x=0, color=config.get_qt_color('endMarker'), 
                                          linestyle='-', linewidth=1, alpha=0.8, visible=False)
            
            # For mono compatibility
            self.ax_left = self.ax
            self.ax_right = None
            self.line_left = self.line
            self.line_right = None
            self.start_marker_left = self.start_marker
            self.end_marker_left = self.end_marker
            self.start_marker_right = None
            self.end_marker_right = None
        
        # Initialize triangle handles (they'll be created properly when markers are shown)
        self.start_marker_handle = None
        self.end_marker_handle = None
        
        # Initialize triangle handles with empty data
        self._create_marker_handles()
        
        # Add the matplotlib canvas to the layout
        self.layout.addWidget(self.canvas)
        
        # Connect event handlers
        self.cid_press = self.canvas.mpl_connect('button_press_event', self._on_plot_click)
        self.cid_release = self.canvas.mpl_connect('button_release_event', self._on_button_release)
        self.cid_motion = self.canvas.mpl_connect('motion_notify_event', self._on_motion_notify)
        
        # No highlight functionality
    
    def _create_marker_handles(self):
        """Create directional triangle handles for both markers"""
        from matplotlib.patches import Polygon
        import numpy as np
        
        # Create empty triangles initially
        empty_triangle = np.array([[0, 0], [0, 0], [0, 0]])
        
        # Set marker properties
        start_marker_props = {
            'closed': True,
            'color': config.get_qt_color('startMarker'),
            'fill': True,
            'alpha': 1.0,
            'visible': True,
            'zorder': 100,
            'label': 'start_marker_handle',
            'linewidth': 1.5
        }
        
        end_marker_props = {
            'closed': True,
            'color': config.get_qt_color('endMarker'),
            'fill': True,
            'alpha': 1.0,
            'visible': True,
            'zorder': 100,
            'label': 'end_marker_handle',
            'linewidth': 1.5
        }
        
        # Create the start marker handle
        if self.start_marker_handle is not None:
            try:
                self.start_marker_handle.remove()
            except:
                pass
                
        self.start_marker_handle = Polygon(empty_triangle, **start_marker_props)
        self.ax.add_patch(self.start_marker_handle)
        
        # Create the end marker handle
        if self.end_marker_handle is not None:
            try:
                self.end_marker_handle.remove()
            except:
                pass
                
        self.end_marker_handle = Polygon(empty_triangle, **end_marker_props)
        self.ax.add_patch(self.end_marker_handle)
    
    def _update_marker_handle(self, marker_type):
        """Update the position of a marker's triangle handle"""
        import numpy as np
        
        # Get the current axis dimensions
        x_min, x_max = self.ax.get_xlim()
        y_min, y_max = self.ax.get_ylim()
        
        # Set fixed data sizes for triangles
        triangle_height_data = self.total_time * 0.02  # 2% of total duration
        triangle_base_half_data = self.total_time * 0.015  # 1.5% of total duration
        
        if marker_type == 'start':
            marker = self.start_marker
            handle = self.start_marker_handle
        else:  # end marker
            marker = self.end_marker
            handle = self.end_marker_handle
            
        # Ensure marker and handle exist
        if marker is None or handle is None:
            return
        
        # Force marker to be visible
        if not marker.get_visible():
            marker.set_visible(True)
            
        # Get marker position
        marker_x = marker.get_xdata()[0]
        
        # Position triangle at the bottom of the waveform
        base_y = y_min
        
        # Create right triangle coordinates
        if marker_type == 'start':
            # Start marker: Right triangle that points RIGHT (→)
            triangle_coords = np.array([
                [marker_x, base_y],  # Bottom center point
                [marker_x + triangle_base_half_data, base_y],  # Bottom-right
                [marker_x, base_y + triangle_height_data]  # Top center point
            ])
        else:  # end marker
            # End marker: Right triangle that points LEFT (←)
            triangle_coords = np.array([
                [marker_x, base_y],  # Bottom center point
                [marker_x - triangle_base_half_data, base_y],  # Bottom-left
                [marker_x, base_y + triangle_height_data]  # Top center point
            ])
        
        # Update the triangle
        handle.set_xy(triangle_coords)
        handle.set_visible(True)
        handle.set_zorder(100)  # Ensure triangles are always on top
    
    def _on_plot_click(self, event):
        """Handle plot click event"""
        # Check if click is in one of the axes
        if event.inaxes not in [self.ax_left, self.ax_right]:
            return
        
        # Check if clicking near a marker
        start_marker_x = self.start_marker.get_xdata()[0] if self.start_marker and self.start_marker.get_visible() else None
        end_marker_x = self.end_marker.get_xdata()[0] if self.end_marker and self.end_marker.get_visible() else None
        
        # Enhanced detection for markers - 0.1s threshold
        if start_marker_x is not None and abs(event.xdata - start_marker_x) < 0.1:
            self.dragging_marker = 'start'
            return
        elif end_marker_x is not None and abs(event.xdata - end_marker_x) < 0.1:
            self.dragging_marker = 'end'
            return
        
        # Emit signal for segment click
        self.segment_clicked.emit(event.xdata)
    
    def _on_button_release(self, event):
        """Handle button release event"""
        if self.dragging_marker:
            # Get the marker position
            position = self.start_marker.get_xdata()[0] if self.dragging_marker == 'start' else self.end_marker.get_xdata()[0]
            
            # Emit the marker released signal
            self.marker_released.emit(self.dragging_marker, position)
            
            # Reset dragging state
            self.dragging_marker = None
    
    def _on_motion_notify(self, event):
        """Handle mouse movement for dragging markers"""
        if not self.dragging_marker or event.inaxes not in [self.ax_left, self.ax_right]:
            return
        
        # Update marker position
        if self.dragging_marker == 'start':
            # Ensure start marker doesn't go past end marker
            if self.end_marker.get_visible():
                end_x = self.end_marker.get_xdata()[0]
                if event.xdata >= end_x:
                    return
            self.set_start_marker(event.xdata)
            self.marker_dragged.emit('start', event.xdata)
        elif self.dragging_marker == 'end':
            # Ensure end marker doesn't go before start marker
            if self.start_marker.get_visible():
                start_x = self.start_marker.get_xdata()[0]
                if event.xdata <= start_x:
                    return
            self.set_end_marker(event.xdata)
            self.marker_dragged.emit('end', event.xdata)
        
        self.canvas.draw()
    
    def update_plot(self, time, data_left, data_right=None):
        """Update the plot with new audio data"""
        if self.stereo_display and data_right is not None:
            # Stereo display - update both channels
            self.line_left.set_data(time, data_left)
            self.line_right.set_data(time, data_right)
            
            # Set identical x limits for both subplots
            self.ax_left.set_xlim(time[0], time[-1])
            self.ax_right.set_xlim(time[0], time[-1])
            
            # Set y limits based on each channel's min/max
            self.ax_left.set_ylim(min(data_left), max(data_left))
            self.ax_right.set_ylim(min(data_right), max(data_right))
        else:
            # Mono display - update single plot
            self.line_left.set_data(time, data_left)
            self.ax_left.set_xlim(time[0], time[-1])
            self.ax_left.set_ylim(min(data_left), max(data_left))
        
        # Update the triangle handles if needed
        if self.start_marker.get_visible() and self.start_marker_handle:
            self._update_marker_handle('start')
            
        if self.end_marker.get_visible() and self.end_marker_handle:
            self._update_marker_handle('end')
            
        self.canvas.draw()
    
    def update_slices(self, slices, total_time=None):
        """Update the segment slices displayed on the waveform"""
        if total_time is not None:
            self.total_time = total_time
        
        # Save references
        self.current_slices = slices
        
        # Save marker states
        start_visible = True
        end_visible = True
        
        # Get current marker positions or use default values
        start_pos = self.start_marker.get_xdata()[0] if hasattr(self.start_marker, 'get_xdata') and self.start_marker else 0
        end_pos = self.end_marker.get_xdata()[0] if hasattr(self.end_marker, 'get_xdata') and self.end_marker else self.total_time
        
        # If end marker is too close to start, adjust it
        if abs(end_pos - start_pos) < 0.1:
            end_pos = self.total_time
        
        # Clear existing slice lines
        if self.stereo_display:
            # Clear previous lines except the main waveform plot lines
            for line in self.ax_left.lines[1:]:
                line.remove()
            for line in self.ax_right.lines[1:]:
                line.remove()
                
            # Re-add our markers
            self.start_marker_left = self.ax_left.axvline(x=start_pos, color=config.get_qt_color('startMarker'), 
                                                      linestyle='-', linewidth=2, alpha=0.8, visible=True)
            self.end_marker_left = self.ax_left.axvline(x=end_pos, color=config.get_qt_color('endMarker'), 
                                                    linestyle='-', linewidth=2, alpha=0.8, visible=True)
            
            self.start_marker_right = self.ax_right.axvline(x=start_pos, color=config.get_qt_color('startMarker'), 
                                                        linestyle='-', linewidth=2, alpha=0.8, visible=True)
            self.end_marker_right = self.ax_right.axvline(x=end_pos, color=config.get_qt_color('endMarker'), 
                                                      linestyle='-', linewidth=2, alpha=0.8, visible=True)
            
            # Plot new slice lines on both subplots
            for slice_time in slices:
                self.ax_left.axvline(x=slice_time, color=config.get_qt_color('sliceActive'), linestyle='--', alpha=0.5)
                self.ax_right.axvline(x=slice_time, color=config.get_qt_color('sliceActive'), linestyle='--', alpha=0.5)
            
            # Update references for event handling
            self.start_marker = self.start_marker_left
            self.end_marker = self.end_marker_left
        else:
            # Clear previous lines except the main waveform plot line
            for line in self.ax.lines[1:]:
                line.remove()
                
            # Re-add our markers
            self.start_marker = self.ax.axvline(x=start_pos, color=config.get_qt_color('startMarker'), 
                                            linestyle='-', linewidth=2, alpha=0.8, visible=True)
            self.end_marker = self.ax.axvline(x=end_pos, color=config.get_qt_color('endMarker'), 
                                          linestyle='-', linewidth=2, alpha=0.8, visible=True)
            
            # Update references for mono compatibility
            self.start_marker_left = self.start_marker
            self.end_marker_left = self.end_marker
            
            # Plot new slice lines
            for slice_time in slices:
                self.ax.axvline(x=slice_time, color=config.get_qt_color('sliceActive'), linestyle='--', alpha=0.5)
        
        # Recreate the triangle handles
        self._create_marker_handles()
        
        # Always update both marker handles
        self._update_marker_handle('start')
        self._update_marker_handle('end')
        
        self.canvas.draw()
    
    def set_start_marker(self, position):
        """Set the position of the start marker"""
        # Snap to start of waveform if within threshold
        if position < self.snap_threshold:
            position = 0.0
        
        # If end marker exists, ensure start marker is before it
        if self.end_marker.get_visible():
            end_x = self.end_marker.get_xdata()[0]
            position = min(position, end_x - 0.01)
        
        # Update the marker in primary subplot
        self.start_marker.set_xdata([position, position])
        self.start_marker.set_visible(True)
        
        # If in stereo mode, also update the second marker
        if self.stereo_display and self.start_marker_right is not None:
            self.start_marker_right.set_xdata([position, position])
            self.start_marker_right.set_visible(True)
        
        # Update the triangle handle
        self._update_marker_handle('start')
        
        self.canvas.draw()
    
    def set_end_marker(self, position):
        """Set the position of the end marker"""
        # Snap to end of waveform if within threshold
        if self.total_time and (self.total_time - position) < self.snap_threshold:
            position = self.total_time
        
        # If start marker exists, ensure end marker is after it
        if self.start_marker.get_visible():
            start_x = self.start_marker.get_xdata()[0]
            position = max(position, start_x + 0.01)
        
        # Update the marker in primary subplot
        self.end_marker.set_xdata([position, position])
        self.end_marker.set_visible(True)
        
        # If in stereo mode, also update the second marker
        if self.stereo_display and self.end_marker_right is not None:
            self.end_marker_right.set_xdata([position, position])
            self.end_marker_right.set_visible(True)
        
        # Update the triangle handle
        self._update_marker_handle('end')
        
        self.canvas.draw()
    
    def get_marker_positions(self):
        """Get the positions of both markers, or None if not visible"""
        start_pos = self.start_marker.get_xdata()[0] if self.start_marker.get_visible() else None
        end_pos = self.end_marker.get_xdata()[0] if self.end_marker.get_visible() else None
        return start_pos, end_pos
    
    def highlight_active_segment(self, start_time, end_time):
        """Highlight the currently playing segment"""
        # Clear any existing highlight
        self.clear_active_segment_highlight()
        
        # Create new highlight spans
        if self.stereo_display:
            # Highlight in both waveforms
            self.active_segment_highlight = self.ax_left.axvspan(
                start_time, end_time, 
                color=config.get_qt_color('activeSegmentHighlight'), 
                alpha=0.25, zorder=5
            )
            self.active_segment_highlight_right = self.ax_right.axvspan(
                start_time, end_time, 
                color=config.get_qt_color('activeSegmentHighlight'), 
                alpha=0.25, zorder=5
            )
        else:
            # Just highlight in the single waveform for mono
            self.active_segment_highlight = self.ax.axvspan(
                start_time, end_time, 
                color=config.get_qt_color('activeSegmentHighlight'), 
                alpha=0.25, zorder=5
            )
        
        # Update display
        self.canvas.draw()
    
    def clear_active_segment_highlight(self):
        """Remove the active segment highlight"""
        if self.active_segment_highlight:
            self.active_segment_highlight.remove()
            self.active_segment_highlight = None
            
        if self.active_segment_highlight_right:
            self.active_segment_highlight_right.remove()
            self.active_segment_highlight_right = None
            
        # Update display
        self.canvas.draw()


class PyQtGraphWaveformView(BaseWaveformView):
    """PyQtGraph implementation of the waveform visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Enable antialiasing for smoother drawing
        pg.setConfigOptions(antialias=True)
        
        # Initialize properties
        self.time_data = None
        self.active_segment_items = []
        self.marker_handles = {}  # Store handles for markers
        
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create graphics layout widget
        self.graphics_layout = pg.GraphicsLayoutWidget()
        
        # Set background color
        self.graphics_layout.setBackground(QColor(config.get_qt_color('background')))
        
        # Configure plots based on stereo/mono setting
        if self.stereo_display:
            # Create two plots for stereo display
            self.plot_left = self.graphics_layout.addPlot(row=0, col=0)
            self.plot_right = self.graphics_layout.addPlot(row=1, col=0)
            
            # Link x-axes for synchronized scrolling and zooming
            self.plot_right.setXLink(self.plot_left)
            
            # Create plot data items for waveforms
            self.waveform_left = pg.PlotDataItem(pen=self._create_pen('waveform'))
            self.waveform_right = pg.PlotDataItem(pen=self._create_pen('waveform'))
            
            # Add waveforms to plots
            self.plot_left.addItem(self.waveform_left)
            self.plot_right.addItem(self.waveform_right)
            
            # Create vertical line items for markers on both plots with enhanced visibility
            self.start_marker_left = pg.InfiniteLine(
                pos=0, angle=90, movable=True, 
                pen=self._create_pen('startMarker', width=3),
                hoverPen=self._create_pen('startMarker', width=5)
            )
            self.end_marker_left = pg.InfiniteLine(
                pos=0, angle=90, movable=True, 
                pen=self._create_pen('endMarker', width=3),
                hoverPen=self._create_pen('endMarker', width=5)
            )
            self.start_marker_right = pg.InfiniteLine(
                pos=0, angle=90, movable=True, 
                pen=self._create_pen('startMarker', width=3),
                hoverPen=self._create_pen('startMarker', width=5)
            )
            self.end_marker_right = pg.InfiniteLine(
                pos=0, angle=90, movable=True, 
                pen=self._create_pen('endMarker', width=3),
                hoverPen=self._create_pen('endMarker', width=5)
            )
            
            # Add markers to plots
            self.plot_left.addItem(self.start_marker_left)
            self.plot_left.addItem(self.end_marker_left)
            self.plot_right.addItem(self.start_marker_right)
            self.plot_right.addItem(self.end_marker_right)
            
            # Configure plots
            for plot in [self.plot_left, self.plot_right]:
                plot.showAxis('bottom', False)
                plot.setMouseEnabled(x=False, y=False)  # Disable panning with mouse drag
                plot.getViewBox().enableAutoRange(axis='x', enable=False)  # Disable auto range
                plot.getViewBox().enableAutoRange(axis='y', enable=True)   # Auto range y-axis only
                plot.setMenuEnabled(False)
            
            # Set references for active plot
            self.active_plot = self.plot_left
            self.start_marker = self.start_marker_left
            self.end_marker = self.end_marker_left
        else:
            # Create a single plot for mono display
            self.plot_left = self.graphics_layout.addPlot(row=0, col=0)
            
            # Create plot data item for waveform
            self.waveform_left = pg.PlotDataItem(pen=self._create_pen('waveform'))
            
            # Add waveform to plot
            self.plot_left.addItem(self.waveform_left)
            
            # Create vertical line items for markers with enhanced visibility
            self.start_marker_left = pg.InfiniteLine(
                pos=0, angle=90, movable=True, 
                pen=self._create_pen('startMarker', width=3),
                hoverPen=self._create_pen('startMarker', width=5)
            )
            self.end_marker_left = pg.InfiniteLine(
                pos=0, angle=90, movable=True, 
                pen=self._create_pen('endMarker', width=3),
                hoverPen=self._create_pen('endMarker', width=5)
            )
            
            # Add markers to plot
            self.plot_left.addItem(self.start_marker_left)
            self.plot_left.addItem(self.end_marker_left)
            
            # Configure plot
            self.plot_left.showAxis('bottom', False)
            self.plot_left.setMouseEnabled(x=False, y=False)  # Disable panning with mouse drag
            self.plot_left.getViewBox().enableAutoRange(axis='x', enable=False)  # Disable auto range
            self.plot_left.getViewBox().enableAutoRange(axis='y', enable=True)   # Auto range y-axis only
            self.plot_left.setMenuEnabled(False)
            
            # Set references for active plot
            self.active_plot = self.plot_left
            self.start_marker = self.start_marker_left
            self.end_marker = self.end_marker_left
            
            # Set empty references for single-channel compatibility
            self.plot_right = None
            self.waveform_right = None
            self.start_marker_right = None
            self.end_marker_right = None
        
        # Connect signals for marker interaction
        self._connect_marker_signals()
        
        # Add the graphics layout widget to the main layout
        self.layout.addWidget(self.graphics_layout)
    
    def _create_pen(self, color_key, width=1):
        """Create a pen with the specified color and width"""
        color = QColor(config.get_qt_color(color_key))
        return pg.mkPen(color=color, width=width)
    
    def _connect_marker_signals(self):
        """Connect signals for marker interaction"""
        # Connect marker position changed signals
        self.start_marker.sigPositionChanged.connect(lambda: self._on_marker_dragged('start'))
        self.end_marker.sigPositionChanged.connect(lambda: self._on_marker_dragged('end'))
        
        # Connect plot click signals
        self.graphics_layout.scene().sigMouseClicked.connect(self._on_plot_clicked)
        
        # Disable right-click context menu
        for plot in [p for p in [self.plot_left, self.plot_right] if p is not None]:
            # Completely disable right-click menu
            plot.getViewBox().menu = None
    
    def _update_marker_handle(self, marker_type):
        """Create or update marker handle triangle"""
        # Get marker position
        if marker_type == 'start':
            marker = self.start_marker
            color = config.get_qt_color('startMarker')
        else:
            marker = self.end_marker
            color = config.get_qt_color('endMarker')
            
        position = marker.value()
        
        # Remove old handle if exists
        handle_key = f"{marker_type}_handle"
        if handle_key in self.marker_handles:
            handle = self.marker_handles[handle_key]
            if handle in self.active_plot.items:
                self.active_plot.removeItem(handle)
                
        # Calculate triangle size based on total time
        triangle_height = self.total_time * 0.02  # 2% of total time
        triangle_width = self.total_time * 0.01   # 1% of total time
        
        # Get the plot Y range to position triangles at the bottom
        y_min, y_max = self.active_plot.getViewBox().viewRange()[1]
        
        # Create points for triangle anchored to the bottom edge
        if marker_type == 'start':
            # Right-pointing triangle
            triangle = [
                (position, y_min),                      # Bottom point
                (position + triangle_width, y_min),     # Bottom right point
                (position, y_min + triangle_height)     # Top point
            ]
        else:
            # Left-pointing triangle
            triangle = [
                (position, y_min),                      # Bottom point
                (position - triangle_width, y_min),     # Bottom left point
                (position, y_min + triangle_height)     # Top point
            ]
            
        # Create polygon item
        handle = pg.PlotDataItem(
            x=[p[0] for p in triangle],
            y=[p[1] for p in triangle],
            fillLevel=0,
            fillBrush=QColor(color),
            pen=pg.mkPen(color=QColor(color), width=2)
        )
        
        # Add to plot and store reference
        self.active_plot.addItem(handle)
        self.marker_handles[handle_key] = handle
    
    def _on_marker_dragged(self, marker_type):
        """Handle marker drag events"""
        if marker_type == 'start':
            # Get current marker position
            position = self.start_marker.value()
            
            # Apply constraints for valid start marker positions
            position = max(0.0, position)  # Never less than 0
            
            # Ensure start marker doesn't go beyond end marker
            end_pos = self.end_marker.value()
            position = min(position, end_pos - 0.01)
            
            # Apply position with constraints
            self.start_marker.setValue(position)
            
            # Update other markers in stereo mode
            if self.stereo_display and self.start_marker_right is not None:
                self.start_marker_right.setValue(position)
        else:  # 'end'
            # Get current marker position
            position = self.end_marker.value()
            
            # Apply constraints for valid end marker positions
            position = max(0.0, position)  # Never less than 0
            if self.total_time > 0:
                position = min(position, self.total_time)  # Never beyond total_time
            
            # Ensure end marker doesn't go before start marker
            start_pos = self.start_marker.value()
            position = max(position, start_pos + 0.01)
            
            # Apply position with constraints
            self.end_marker.setValue(position)
            
            # Update other markers in stereo mode
            if self.stereo_display and self.end_marker_right is not None:
                self.end_marker_right.setValue(position)
        
        # Update marker handle
        self._update_marker_handle(marker_type)
        
        # Emit signal for controller
        self.marker_dragged.emit(marker_type, position)
    
    def _on_plot_clicked(self, event):
        """Handle plot click events"""
        
        # Only process left button clicks
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        # Get mouse position in scene coordinates
        scene_pos = event.scenePos()
        
        # Check which plot was clicked
        for plot, marker in [(self.plot_left, self.start_marker_left), 
                           (self.plot_right, self.start_marker_right)]:
            if plot is None:
                continue
                
            view_box = plot.getViewBox()
            if view_box.sceneBoundingRect().contains(scene_pos):
                # Convert scene position to data coordinates
                data_pos = view_box.mapSceneToView(scene_pos)
                x_pos = data_pos.x()
                
                # Check if near a marker (high priority)
                start_pos = self.start_marker.value()
                end_pos = self.end_marker.value()
                
                # If near the start marker
                if abs(x_pos - start_pos) < 0.1:
                    return  # Let the marker's drag handle this
                
                # If near the end marker
                if abs(x_pos - end_pos) < 0.1:
                    return  # Let the marker's drag handle this
                
                # Emit segment clicked signal
                self.segment_clicked.emit(x_pos)
                return
    
    def update_plot(self, time, data_left, data_right=None):
        """Update the plot with new audio data"""
        # Save reference to time data
        self.time_data = time
        
        # Update left channel
        self.waveform_left.setData(time, data_left)
        
        # Set view ranges for left channel
        self.plot_left.setXRange(time[0], time[-1], padding=0)
        y_max_left = max(abs(data_left.min()), abs(data_left.max()))
        self.plot_left.setYRange(-y_max_left, y_max_left, padding=0.1)
        
        # Update right channel if stereo
        if self.stereo_display and data_right is not None and self.waveform_right is not None:
            self.waveform_right.setData(time, data_right)
            
            # Set view ranges for right channel
            self.plot_right.setXRange(time[0], time[-1], padding=0)
            y_max_right = max(abs(data_right.min()), abs(data_right.max()))
            self.plot_right.setYRange(-y_max_right, y_max_right, padding=0.1)
            
        # Update marker handles
        self._update_marker_handle('start')
        self._update_marker_handle('end')
    
    def update_slices(self, slices, total_time=None):
        """Update the segment slices displayed on the waveform"""
        if total_time is not None:
            self.total_time = total_time
        
        # Save current slices
        self.current_slices = slices
        
        # Get current marker positions
        start_pos = self.start_marker.value()
        end_pos = self.end_marker.value()
        
        # Ensure start and end markers are sufficiently separated
        if abs(end_pos - start_pos) < 0.1:
            end_pos = self.total_time
            self.set_end_marker(end_pos)
        
        # Clear existing slice markers
        self._clear_segment_markers()
        
        # Add slice markers
        for plot in [self.plot_left, self.plot_right]:
            if plot is None:
                continue
                
            # Add new slice markers
            for slice_time in slices:
                line = pg.InfiniteLine(
                    pos=slice_time,
                    angle=90,
                    movable=False,
                    pen=self._create_pen('sliceActive', width=1)
                )
                plot.addItem(line)
        
        # Update marker handles for both markers
        self._update_marker_handle('start')
        self._update_marker_handle('end')
    
    def _clear_segment_markers(self):
        """Clear all segment markers from the plots"""
        
        # For each plot
        for plot in [self.plot_left, self.plot_right]:
            if plot is None:
                continue
                
            # Get all items in the plot
            items = plot.items.copy()
            
            # Remove all InfiniteLine items that aren't start/end markers
            for item in items:
                if (isinstance(item, pg.InfiniteLine) and 
                    item not in [self.start_marker_left, self.end_marker_left, 
                                self.start_marker_right, self.end_marker_right]):
                    plot.removeItem(item)
    
    def set_start_marker(self, position):
        """Set the position of the start marker"""
        # Ensure position is within valid range (never less than 0)
        position = max(0.0, position)
        
        # Apply snapping if close to the start
        if position < self.snap_threshold:
            position = 0.0
        
        # Ensure start marker doesn't go beyond end marker
        end_pos = self.end_marker.value()
        position = min(position, end_pos - 0.01)
        
        # Update markers
        self.start_marker.setValue(position)
        
        # Update stereo view if needed
        if self.stereo_display and self.start_marker_right is not None:
            self.start_marker_right.setValue(position)
            
        # Update triangle marker handle
        self._update_marker_handle('start')
    
    def set_end_marker(self, position):
        """Set the position of the end marker"""
        # Ensure position is within valid range (never less than 0 or greater than total_time)
        position = max(0.0, position)
        if self.total_time > 0:
            position = min(position, self.total_time)
            
        # Apply snapping if close to the end
        if self.total_time > 0 and (self.total_time - position) < self.snap_threshold:
            position = self.total_time
        
        # Ensure end marker doesn't go before start marker
        start_pos = self.start_marker.value()
        position = max(position, start_pos + 0.01)
        
        # Update markers
        self.end_marker.setValue(position)
        
        # Update stereo view if needed
        if self.stereo_display and self.end_marker_right is not None:
            self.end_marker_right.setValue(position)
            
        # Update triangle marker handle
        self._update_marker_handle('end')
    
    def get_marker_positions(self):
        """Get the positions of both markers"""
        if not self.start_marker or not self.end_marker:
            return None, None
            
        return self.start_marker.value(), self.end_marker.value()
    
    def highlight_active_segment(self, start_time, end_time):
        """Highlight the currently playing segment"""
        
        # Clear any existing highlight
        self.clear_active_segment_highlight()
        
        # Get highlight color
        color = QColor(config.get_qt_color('activeSegmentHighlight'))
        color.setAlpha(64)  # 25% opacity
        
        # Create brushes for filling
        brush = QBrush(color)
        
        # Create linear regions (highlighted spans)
        for plot in [self.plot_left, self.plot_right]:
            if plot is None:
                continue
                
            # Create a linear region item
            region = pg.LinearRegionItem(
                values=[start_time, end_time],
                movable=False,
                brush=brush
            )
            region.setZValue(0)  # Behind waveform but above background
            
            # Add to plot and track in active segment items
            plot.addItem(region)
            self.active_segment_items.append(region)
    
    def clear_active_segment_highlight(self):
        """Remove the active segment highlight"""
        # Remove all active segment highlights
        for item in self.active_segment_items:
            if item.scene() is not None:  # Only remove if still in a scene
                item.scene().removeItem(item)
        
        # Clear the list
        self.active_segment_items = []


def create_waveform_view(backend='matplotlib', parent=None):
    """Factory function to create appropriate waveform view based on backend"""
    # Read from config if not specified
    if backend == 'auto':
        backend = config.get_value_from_json_file("audio.json", "backend", "matplotlib")
    
    # Create the appropriate view
    if backend == 'pyqtgraph':
        return PyQtGraphWaveformView(parent)
    else:
        return MatplotlibWaveformView(parent)