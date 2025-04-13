"""
Waveform visualization using PyQtGraph.
This module provides efficient waveform visualization for the RCY application.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPen, QBrush
from config_manager import config
import pyqtgraph as pg


class BaseWaveformView(QWidget):
    """Base class for waveform visualization"""
    # Define signals
    marker_dragged = pyqtSignal(str, float)   # (marker_type, position)
    segment_clicked = pyqtSignal(float)       # (x_position)
    marker_released = pyqtSignal(str, float)  # (marker_type, position)
    add_segment = pyqtSignal(float)           # (x_position)
    remove_segment = pyqtSignal(float)        # (x_position)
    
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




class PyQtGraphWaveformView(BaseWaveformView):
    """PyQtGraph implementation of the waveform visualization"""
    
    def __init__(self, parent=None):
        # Check if PyQtGraph is available before proceeding
        if not PYQTGRAPH_AVAILABLE:
            raise ImportError("PyQtGraph is not available")
            
        super().__init__(parent)
        
        # Enable antialiasing for smoother drawing
        try:
            pg.setConfigOptions(antialias=True)
        except Exception as e:
            print(f"Warning: Could not set PyQtGraph config options: {e}")
        
        # Initialize properties
        self.time_data = None
        self.active_segment_items = []
        self.marker_handles = {}  # Store handles for markers
        
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create graphics layout widget within a try-except block
        try:
            self.graphics_layout = pg.GraphicsLayoutWidget()
            
            # Set background color
            self.graphics_layout.setBackground(QColor(config.get_qt_color('background')))
        except Exception as e:
            print(f"ERROR: Failed to create PyQtGraph layout widget: {e}")
            raise
        
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
        
        # Get keyboard modifiers
        modifiers = QApplication.keyboardModifiers()
        print(f"PyQtGraph modifiers: {modifiers}")
        print(f"Is Control: {bool(modifiers & Qt.KeyboardModifier.ControlModifier)}")
        print(f"Is Alt: {bool(modifiers & Qt.KeyboardModifier.AltModifier)}")
        print(f"Is Meta: {bool(modifiers & Qt.KeyboardModifier.MetaModifier)}")
        
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
                
                # Check for keyboard modifiers
                
                # Check for Ctrl+Alt (Option) combination for removing segments
                if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.AltModifier):
                    print(f"Ctrl+Alt (Option) combination detected - removing segment at {x_pos}")
                    try:
                        self.remove_segment.emit(x_pos)
                        print("Emitted remove_segment signal successfully")
                    except Exception as e:
                        print(f"ERROR emitting remove_segment signal: {e}")
                    return
                    
                # Check for Alt+Cmd (Meta) combination for removing segments
                if (modifiers & Qt.KeyboardModifier.AltModifier) and (modifiers & Qt.KeyboardModifier.MetaModifier):
                    print(f"Alt+Cmd combination detected - removing segment at {x_pos}")
                    try:
                        self.remove_segment.emit(x_pos)
                        print("Emitted remove_segment signal successfully")
                    except Exception as e:
                        print(f"ERROR emitting remove_segment signal: {e}")
                    return
                    
                # Add segment with Ctrl+Click
                if modifiers & Qt.KeyboardModifier.ControlModifier:
                    print(f"Ctrl detected - adding segment at {x_pos}")
                    self.add_segment.emit(x_pos)
                    return
                
                # Add segment with Alt+Click
                if modifiers & Qt.KeyboardModifier.AltModifier:
                    print(f"Alt detected - adding segment at {x_pos}")
                    self.add_segment.emit(x_pos)
                    return
                
                # No modifiers - emit regular segment click
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
    
    def get_view_center(self):
        """Get the center position of the current view"""
        if self.active_plot is None:
            return 0
            
        # Get the current view range
        x_min, x_max = self.active_plot.getViewBox().viewRange()[0]
        
        # Return the center position
        return (x_min + x_max) / 2
        
    def highlight_segment(self, start_time, end_time, temporary=False):
        """Highlight a segment of the waveform
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            temporary: If True, uses a different color for temporary highlights
        """
        # Use different colors for temporary vs active highlights
        if temporary:
            color_key = 'selectionHighlight'
            alpha = 75  # ~30%
        else:
            color_key = 'activeSegmentHighlight'
            alpha = 64  # 25%
            
        # Get highlight color
        color = QColor(config.get_qt_color(color_key))
        color.setAlpha(alpha)
        
        # Create brushes for filling
        brush = QBrush(color)
        
        # Clear existing highlights (if for the same purpose)
        if not temporary:
            self.clear_active_segment_highlight()
        
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


def create_waveform_view(parent=None):
    """Create a PyQtGraph-based waveform view"""
    return PyQtGraphWaveformView(parent)