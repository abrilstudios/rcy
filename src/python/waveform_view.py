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
        # TODO: Unify handling of config - do not allow get_value_from_json
        self.stereo_display = config.get_setting("audio", "stereoDisplay", True)
    
    def update_plot(self, time, data_left, data_right=None, is_stereo=False):
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
        
        # Initialize properties for marker handles
        # Required for consistent visual presentation
        self.handle_y_min = -1.0  # Used to place markers at bottom of view
        
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
        
        # Connect marker drag finished signals
        self.start_marker.sigPositionChangeFinished.connect(lambda: self._on_marker_drag_finished('start'))
        self.end_marker.sigPositionChangeFinished.connect(lambda: self._on_marker_drag_finished('end'))
        
        # Connect plot click signals
        self.graphics_layout.scene().sigMouseClicked.connect(self._on_plot_clicked)
        
        # Disable right-click context menu
        for plot in [p for p in [self.plot_left, self.plot_right] if p is not None]:
            # Completely disable right-click menu
            plot.getViewBox().menu = None
    
    def _update_marker_handle(self, marker_type):
        """Create or update rectangular marker handle with a fixed pixel size"""
        # Make sure we have valid time data
        if self.time_data is None:
            return
            
        # Fix for TypeError: object of type 'NoneType' has no len()
        try:
            if len(self.time_data) == 0:
                return
        except TypeError:
            return
        
        # Get marker reference
        if marker_type == 'start':
            marker = self.start_marker
            color = config.get_qt_color('startMarker')
        else:
            marker = self.end_marker
            color = config.get_qt_color('endMarker')
            
        # Ensure marker exists
        if marker is None:
            return
            
        try:
            position = marker.value()
            if position is None:
                return
        except Exception as e:
            return
        
        # Get valid data range
        min_pos = self.time_data[0]
        max_pos = self.time_data[-1]
        
        # Guard clause: Don't draw handles for markers outside data range
        if position < min_pos or position > max_pos:
            
            # Remove existing handle if there is one
            handle_key = f"{marker_type}_handle"
            if handle_key in self.marker_handles:
                handle = self.marker_handles[handle_key]
                if handle is not None and self.active_plot is not None and handle in self.active_plot.items:
                    self.active_plot.removeItem(handle)
                    self.marker_handles[handle_key] = None
            return
        
        # Ensure active plot exists
        if self.active_plot is None:
            return
            
        
        # Remove old handle if exists
        handle_key = f"{marker_type}_handle"
        if handle_key in self.marker_handles:
            handle = self.marker_handles[handle_key]
            if handle is not None and handle in self.active_plot.items:
                self.active_plot.removeItem(handle)
        
        # Get the view box for coordinate transformations
        view_box = self.active_plot.getViewBox()
        if view_box is None:
            return
        
        # Get UI configuration for marker size in pixels
        marker_width_px = config.get_ui_setting("markerHandles", "width", 8)
        marker_height_px = config.get_ui_setting("markerHandles", "height", 14)
        
        # Get current view range and calculate the scale
        try:
            x_range = view_box.viewRange()[0]
            y_range = view_box.viewRange()[1]
            x_min, x_max = x_range
            y_min, y_max = y_range
        except Exception as e:
            return
        
        # Calculate size in data units based on view range
        view_width = view_box.width()  # Width of the view box in pixels
        view_height = view_box.height()  # Height of the view box in pixels
        
        # Defensive check for zero values
        if view_width <= 0 or view_height <= 0:
            return
            
        # Calculate the data units per pixel
        x_scale = (x_max - x_min) / view_width  # data units per pixel horizontally
        y_scale = (y_max - y_min) / view_height  # data units per pixel vertically
        
        # Convert our desired pixel size to data units
        width_in_data = x_scale * marker_width_px
        height_in_data = y_scale * marker_height_px
        
        # Create a rectangle ROI that's properly positioned and sized
        # For both markers, center the rectangle on the marker position
        rect_pos = (position - (width_in_data / 2), y_min)
        
        # Create a simple rectangle with PlotDataItem
        # Create points for a rectangle
        x_points = [
            rect_pos[0], rect_pos[0] + width_in_data, 
            rect_pos[0] + width_in_data, rect_pos[0], rect_pos[0]
        ]
        y_points = [
            rect_pos[1], rect_pos[1], 
            rect_pos[1] + height_in_data, rect_pos[1] + height_in_data, rect_pos[1]
        ]
        
        # Create a filled rectangle using PlotDataItem
        handle = pg.PlotDataItem(
            x=x_points, y=y_points,
            fillLevel=y_min,
            fillBrush=QColor(color),
            pen=pg.mkPen(None)  # No border
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
        print(f"Marker {marker_type} dragged to {position}s")
        self.marker_dragged.emit(marker_type, position)
        
    def _on_marker_drag_finished(self, marker_type):
        """Handle marker drag finished events"""
        if marker_type == 'start':
            position = self.start_marker.value()
        else:  # 'end'
            position = self.end_marker.value()
            
        # Apply final marker bounds check
        self._clamp_markers_to_data_bounds()
        
        # Ensure both handles are updated
        self._update_marker_handle('start')
        self._update_marker_handle('end')
        
        # Emit signal for controller
        print(f"Marker {marker_type} released at {position}s")
        self.marker_released.emit(marker_type, position)
    
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
    
    def update_plot(self, time, data_left, data_right=None, is_stereo=False):
        """Update the plot with new audio data"""
        print(f"\n==== WAVEFORM_VIEW UPDATE_PLOT ====")
        print(f"File is_stereo: {is_stereo}, config stereo_display: {self.stereo_display}")
        
        # Detect if we need to rebuild the view for different stereo mode
        actual_stereo_display = is_stereo  # Use actual file metadata instead of config
        if actual_stereo_display != self.stereo_display:
            print(f"Stereo mode changed: {self.stereo_display} -> {actual_stereo_display}")
            print("Note: This would require rebuilding the view, which is complex.")
            print("For now, showing stereo layout but will be fixed in single plot architecture.")
        
        # Get detailed information about the current state
        old_start_pos = self.start_marker.value() if self.start_marker else None
        old_end_pos = self.end_marker.value() if self.end_marker else None
        try:
            old_max_pos = self.time_data[-1] if self.time_data is not None and len(self.time_data) > 0 else None
        except TypeError:
            old_max_pos = None
        old_total_time = getattr(self, 'total_time', None)
        
        # Check for existing handles
        old_start_handle = self.marker_handles.get('start_handle')
        old_end_handle = self.marker_handles.get('end_handle')
        
        # Save reference to time data
        try:
            if time is not None and len(time) > 0:
                new_max_pos = time[-1]
            else:
                new_max_pos = None
        except TypeError:
            new_max_pos = None
            
        self.time_data = time
        
        # Detail all current properties
        
        # Precheck - would end marker need clamping?
        if old_end_pos is not None and new_max_pos is not None and old_end_pos > new_max_pos:
            print(f"End marker ({old_end_pos}) is beyond new max ({new_max_pos}) - will need clamping")
        
        # Update left channel
        self.waveform_left.setData(time, data_left)
        
        # Set view ranges for left channel
        # No padding to eliminate visual gap at marker end
        padding_value = 0.0  # No padding
        self.plot_left.setXRange(time[0], time[-1], padding=padding_value)
        y_max_left = max(abs(data_left.min()), abs(data_left.max()))
        self.plot_left.setYRange(-y_max_left, y_max_left, padding=0.1)
        
        # Update right channel if actually stereo (use file metadata, not config)
        if is_stereo and data_right is not None and self.waveform_right is not None:
            self.waveform_right.setData(time, data_right)
            
            # Set view ranges for right channel with padding
            self.plot_right.setXRange(time[0], time[-1], padding=padding_value)
            y_max_right = max(abs(data_right.min()), abs(data_right.max()))
            self.plot_right.setYRange(-y_max_right, y_max_right, padding=0.1)
            
            # Show right channel plot for stereo files
            if self.plot_right is not None:
                self.plot_right.setVisible(True)
        else:
            # Hide right channel plot for mono files
            if self.plot_right is not None:
                self.plot_right.setVisible(False)
        
        # Get marker positions immediately after data update but before clamping
        current_start_pos = self.start_marker.value()
        current_end_pos = self.end_marker.value()
        
        if current_end_pos > new_max_pos:
            print(f"Detected end marker ({current_end_pos}) beyond data bounds ({new_max_pos})")
        
        # Check marker handle positions before clamping
        curr_start_handle = self.marker_handles.get('start_handle')
        curr_end_handle = self.marker_handles.get('end_handle')
                
        # Clamp marker positions to valid range after waveform change
        self._clamp_markers_to_data_bounds()
        
        # Get marker positions after clamping
        new_start_pos = self.start_marker.value()
        new_end_pos = self.end_marker.value()
        
        # Verify clamping worked correctly
        if new_max_pos is not None and new_end_pos > new_max_pos:
            print(f"WARNING: End marker ({new_end_pos}) still beyond max ({new_max_pos}) after clamping!")
        else:
            print(f"End marker position after clamping: {new_end_pos}")
        
        # Check marker handles after clamping
        post_start_handle = self.marker_handles.get('start_handle')
        post_end_handle = self.marker_handles.get('end_handle')
                
        # Update marker handles
        self._update_marker_handle('start')
        self._update_marker_handle('end')
        
        # Final check on handles
        final_start_handle = self.marker_handles.get('start_handle')
        final_end_handle = self.marker_handles.get('end_handle')
        
        # Print final marker locations
        final_start_pos = self.start_marker.value()
        final_end_pos = self.end_marker.value()
        print(f"==== END WAVEFORM_VIEW UPDATE_PLOT ====\n")
    
    def update_slices(self, slices, total_time=None):
        """Update the segment slices displayed on the waveform"""
        # Record marker positions before update
        pre_start_pos = self.start_marker.value()
        pre_end_pos = self.end_marker.value()
        
        if total_time is not None:
            old_total_time = getattr(self, 'total_time', None)
            self.total_time = total_time
        
        # Save current slices
        self.current_slices = slices
        
        # Get data boundaries with TypeError protection
        data_max = None
        try:
            if self.time_data is not None and len(self.time_data) > 0:
                data_max = self.time_data[-1]
        except TypeError:
            print("TypeError when getting data_max")
        
        # Ensure markers are within valid bounds
        try:
            if self.time_data is not None and len(self.time_data) > 0:
                self._clamp_markers_to_data_bounds()
        except TypeError:
            print("TypeError when clamping markers")
        
        # Get positions after clamping
        post_start_pos = self.start_marker.value()
        post_end_pos = self.end_marker.value()
        
        # Ensure start and end markers are sufficiently separated
        if abs(post_end_pos - post_start_pos) < 0.1:
            new_end_pos = self.total_time
            self.set_end_marker(new_end_pos)
        
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
        
        # Get final marker positions after all updates
        final_start_pos = self.start_marker.value()
        final_end_pos = self.end_marker.value()
        
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
        # Always print the initial request for debugging
        
        # Get valid data range from time_data
        if self.time_data is not None and len(self.time_data) > 0:
            data_min = self.time_data[0]
            data_max = self.time_data[-1]
            
            # Ensure position is within valid range
            if position < data_min:
                position = data_min
                
            if position > data_max:
                # Start marker shouldn't be beyond the end of the data
                new_pos = max(data_min, data_max - 0.01)
                position = new_pos
        else:
            # If we don't have time data, this is probably initialization
            # Just record the intended position and return
            # Still verify not negative
            position = max(0.0, position)
            self.start_marker.setValue(position)
            
            # Update stereo view if needed
            if self.stereo_display and self.start_marker_right is not None:
                self.start_marker_right.setValue(position)
                
            return
        
        # Apply snapping if close to the start
        if position < self.snap_threshold:
            position = 0.0
        
        # Ensure start marker doesn't go beyond end marker
        if self.end_marker is not None:
            end_pos = self.end_marker.value()
            minimum_gap = 0.01  # Minimum 10ms gap between markers
            if position > end_pos - minimum_gap:
                position = max(0.0, end_pos - minimum_gap)
        
        # Block signals to prevent recursive callbacks
        old_block_state = self.start_marker.blockSignals(True)
        
        # Update marker with final position
        self.start_marker.setValue(position)
        
        # Restore signal state
        self.start_marker.blockSignals(old_block_state)
        
        # Update stereo view if needed
        if self.stereo_display and self.start_marker_right is not None:
            old_block_state = self.start_marker_right.blockSignals(True)
            self.start_marker_right.setValue(position)
            self.start_marker_right.blockSignals(old_block_state)
        
        
        # Remove old handle if it exists
        if 'start_handle' in self.marker_handles and self.marker_handles['start_handle'] is not None:
            self.active_plot.removeItem(self.marker_handles['start_handle'])
            self.marker_handles['start_handle'] = None
        
        # Always update the marker handle to reflect the new position
        self._update_marker_handle('start')
    
    def set_end_marker(self, position):
        """Set the position of the end marker"""
        # Always print the initial request for debugging
        
        # Get valid data range from time_data
        if self.time_data is not None and len(self.time_data) > 0:
            data_min = self.time_data[0]
            data_max = self.time_data[-1]
            
            # CRITICAL FIX: ALWAYS enforce data bounds
            # This ensures the end marker is never beyond the available data
            if position > data_max:
                position = data_max
        else:
            # If we don't have time data, this is probably initialization
            # Just record the intended position and return
            # Still verify not negative
            position = max(0.0, position)
            self.end_marker.setValue(position)
            
            # Update stereo view if needed
            if self.stereo_display and self.end_marker_right is not None:
                self.end_marker_right.setValue(position)
                
            return
        
        # Apply basic validation - never less than data_min (usually 0)
        position = max(data_min, position)
        
        # Ensure end marker doesn't go before start marker
        if self.start_marker is not None:
            start_pos = self.start_marker.value()
            minimum_gap = 0.01  # Minimum 10ms gap between markers
            if position < start_pos + minimum_gap:
                position = start_pos + minimum_gap
        
        # Block signals to prevent recursive callbacks
        old_block_state = self.end_marker.blockSignals(True)
        
        # Update marker with final position
        self.end_marker.setValue(position)
        
        # Restore signal state
        self.end_marker.blockSignals(old_block_state)
        
        # Update stereo view if needed
        if self.stereo_display and self.end_marker_right is not None:
            old_block_state = self.end_marker_right.blockSignals(True)
            self.end_marker_right.setValue(position)
            self.end_marker_right.blockSignals(old_block_state)
        
        
        # Remove old handle if it exists
        if 'end_handle' in self.marker_handles and self.marker_handles['end_handle'] is not None:
            self.active_plot.removeItem(self.marker_handles['end_handle'])
            self.marker_handles['end_handle'] = None
        
        # Always update the marker handle to reflect the new position
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
    
    def _clamp_markers_to_data_bounds(self):
        """Ensure markers stay within valid data boundaries
        
        Called after waveform updates to prevent markers from going outside the valid range,
        which would make their handles invisible or misplaced.
        """
        # Simple version focusing on the core issue: end marker goes beyond data bounds
        try:
            # Make sure we have the essential components and valid data
            if self.time_data is None:
                print("Can't clamp markers: No time data")
                return
                
            # Fix for TypeError: object of type 'NoneType' has no len()
            try:
                if len(self.time_data) == 0:
                    print("Can't clamp markers: Time data is empty")
                    return
            except TypeError:
                print("Can't clamp markers: time_data is not iterable")
                return
                
            if self.end_marker is None:
                print("Can't clamp markers: No end marker")
                return
                
            # Get the max position from time_data
            max_pos = self.time_data[-1]
            
            # Get the end marker position 
            end_pos = self.end_marker.value()
            
            # CRITICAL FIX: Force end marker to max_pos if beyond bounds
            if end_pos > max_pos:
                print(f"Fixing end marker: {end_pos} -> {max_pos}")
                # Block signals during update to prevent recursion
                old_state = self.end_marker.blockSignals(True)
                self.end_marker.setValue(max_pos)
                self.end_marker.blockSignals(old_state)
                
                # Also update stereo marker if present
                if self.stereo_display:
                    if self.end_marker_right is not None:
                        old_state = self.end_marker_right.blockSignals(True)
                        self.end_marker_right.setValue(max_pos)
                        self.end_marker_right.blockSignals(old_state)
                
                # Update the marker handle
                if 'end_handle' in self.marker_handles and self.marker_handles['end_handle'] is not None:
                    if self.active_plot is not None:
                        try:
                            self.active_plot.removeItem(self.marker_handles['end_handle'])
                        except:
                            pass
                self._update_marker_handle('end')
        except Exception as e:
            print(f"Error in _clamp_markers_to_data_bounds: {e}")
            # No matter what happens, don't crash - just return
            return
            
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
