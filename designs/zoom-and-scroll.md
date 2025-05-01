# RCY Zoom and Scroll Design

This document outlines the design and implementation of improved zoom and scroll functionality in the RCY waveform view.

## Background

The current waveform zoom implementation has several limitations:
- It uses a simple scaling factor that doesn't provide consistent zoom steps
- It doesn't preserve view context when zooming (left edge stays fixed)
- It lacks proper zoom bounds enforcement
- It doesn't take full advantage of PyQtGraph's built-in capabilities

## Goals

1. Improve the zoom functionality to be more consistent and intuitive
2. Implement view context preservation during zoom operations
3. Enforce zoom bounds (0.5x to 10x)
4. Better integrate with PyQtGraph's capabilities
5. Enhance the scroll bar interaction with the zoomed view

## Core Concepts

### Zoom Functionality

Zoom modifies the visible time range of the audio waveform. In RCY:
- Only horizontal (X-axis) representing time is affected by zoom
- Vertical scale (amplitude) remains fixed to -1.0 to 1.0
- Zoom should be implemented using PyQtGraph's native mechanisms

### Scroll Functionality

Scroll controls which portion of the audio file is visible when zoomed in:
- Horizontal scrolling shifts the visible time window
- Scroll position should be maintained during zoom operations when possible
- The scroll bar's size should visually indicate the proportion of the file that's visible

## Design Details

### Zoom Implementation Using PyQtGraph

We'll implement zoom using PyQtGraph's `ViewBox.scaleBy()` method, which provides built-in support for scaling around a center point. This approach:

1. Uses native PyQtGraph functionality
2. Automatically preserves view context
3. Requires minimal code changes
4. Provides a better user experience

```python
def zoom_in(self, center=None):
    """Zoom in by a fixed factor, preserving view center"""
    zoom_factor = config.get_setting("zoom", "factor", 1.25)
    self._zoom_by_factor(1.0 / zoom_factor, center)
    
def zoom_out(self, center=None):
    """Zoom out by a fixed factor, preserving view center"""
    zoom_factor = config.get_setting("zoom", "factor", 1.25)
    self._zoom_by_factor(zoom_factor, center)
    
def _zoom_by_factor(self, factor, center=None):
    """Apply zoom by the given factor, enforcing bounds"""
    # Get viewbox from active plot
    view_box = self.active_plot.getViewBox()
    
    # If no center provided, use the current view center
    if center is None:
        x_range = view_box.viewRange()[0]
        center = (x_range[0] + x_range[1]) / 2
    
    # Scale only X-axis (time), keep Y-axis (amplitude) the same
    view_box.scaleBy((factor, 1.0), center=(center, 0))
    
    # Apply zoom bounds
    self._enforce_zoom_bounds()
```

### Zoom Bounds Enforcement

To prevent impractical zoom levels, we'll enforce minimum and maximum zoom bounds:

```python
def _enforce_zoom_bounds(self):
    """Enforce minimum and maximum zoom levels"""
    # Get current view state
    view_box = self.active_plot.getViewBox()
    current_range = view_box.viewRange()[0]
    view_width = current_range[1] - current_range[0]
    center = (current_range[0] + current_range[1]) / 2
    
    # Get zoom bounds from config
    max_scale = config.get_setting("zoom", "maxScale", 10.0)
    min_scale = config.get_setting("zoom", "minScale", 0.5)
    
    # Calculate min/max allowed view widths
    total_time = self.time_data[-1] - self.time_data[0]
    min_width = total_time / max_scale
    max_width = total_time / min_scale
    
    # Enforce bounds
    if view_width < min_width:
        # Too zoomed in, zoom out to limit
        view_box.setRange(xRange=(center - min_width/2, center + min_width/2))
    elif view_width > max_width:
        # Too zoomed out, zoom in to limit
        view_box.setRange(xRange=(center - max_width/2, center + max_width/2))
```

### Scroll Bar Design

The scroll bar should accurately reflect the zoomed state of the waveform view and provide intuitive navigation. We'll enhance the scroll bar functionality with these improvements:

1. **Dynamic Page Size**: The scroll bar's page size should reflect the proportion of the audio file that's currently visible:

```python
def update_scroll_bar(self):
    """Update scroll bar to reflect current view"""
    view_box = self.active_plot.getViewBox()
    x_range = view_box.viewRange()[0]
    
    # Calculate visible proportion of total time
    total_time = self.time_data[-1] - self.time_data[0]
    visible_time = x_range[1] - x_range[0]
    visible_proportion = min(1.0, visible_time / total_time)
    
    # Calculate scroll position as percentage
    scroll_position = (x_range[0] - self.time_data[0]) / (total_time - visible_time) if total_time > visible_time else 0
    
    # Update scroll bar
    self.scroll_bar.blockSignals(True)
    self.scroll_bar.setPageStep(int(visible_proportion * 100))
    self.scroll_bar.setValue(int(scroll_position * 100))
    self.scroll_bar.blockSignals(False)
```

2. **Sync with View**: When the scroll bar is moved, update the view position accordingly:

```python
def on_scroll_value_changed(self, value):
    """Handle scroll bar value change"""
    view_box = self.active_plot.getViewBox()
    x_range = view_box.viewRange()[0]
    visible_time = x_range[1] - x_range[0]
    total_time = self.time_data[-1] - self.time_data[0]
    
    # Calculate new start position based on scroll value
    scroll_proportion = value / 100.0
    new_start = self.time_data[0] + scroll_proportion * (total_time - visible_time)
    
    # Update view position
    view_box.setRange(xRange=(new_start, new_start + visible_time))
```

3. **Bidirectional Sync**: Keep the scroll bar and view in sync regardless of which one initiates the change:

- When the view changes (via zoom, pan, etc.), update the scroll bar
- When the scroll bar changes, update the view
- Use signal blocking to prevent infinite loops

4. **Key and Mouse Wheel Navigation**:

- Add support for keyboard navigation (arrow keys, Page Up/Down)
- Support mouse wheel for both zooming and scrolling (with modifier keys)

```python
def keyPressEvent(self, event):
    """Handle key press events for navigation"""
    view_box = self.active_plot.getViewBox()
    x_range = view_box.viewRange()[0]
    visible_time = x_range[1] - x_range[0]
    
    # Calculate movement amount
    small_step = visible_time * 0.1  # 10% of visible area
    large_step = visible_time * 0.5  # 50% of visible area
    
    if event.key() == Qt.Key.Key_Left:
        # Move left by small step
        self._pan_view(-small_step)
    elif event.key() == Qt.Key.Key_Right:
        # Move right by small step
        self._pan_view(small_step)
    elif event.key() == Qt.Key.Key_PageUp:
        # Move left by large step
        self._pan_view(-large_step)
    elif event.key() == Qt.Key.Key_PageDown:
        # Move right by large step
        self._pan_view(large_step)
    elif event.key() == Qt.Key.Key_Home:
        # Jump to start
        self._jump_to_time(self.time_data[0])
    elif event.key() == Qt.Key.Key_End:
        # Jump to end
        self._jump_to_time(self.time_data[-1] - visible_time)
    else:
        super().keyPressEvent(event)
```

### Mouse Wheel Zoom

We'll also implement mouse wheel zooming for a more interactive experience:

```python
def wheelEvent(self, event):
    """Handle mouse wheel events for zooming"""
    # Get mouse position for center of zoom
    pos = event.position()
    scene_pos = self.active_plot.mapToScene(pos.toPoint())
    view_pos = self.active_plot.getViewBox().mapSceneToView(scene_pos)
    
    # Determine zoom direction based on wheel delta
    delta = event.angleDelta().y()
    if delta > 0:
        # Zoom in at mouse position
        self.zoom_in(center=view_pos.x())
    elif delta < 0:
        # Zoom out at mouse position
        self.zoom_out(center=view_pos.x())
    
    # Update scroll bar after zoom
    self.update_scroll_bar()
    
    # Accept the event to prevent propagation
    event.accept()
```

## Configuration

The zoom and scroll behavior will be configurable via settings in `config.json`:

```json
"zoom": {
  "factor": 1.25,      // Zoom factor per step (e.g., 1.25 = 25% change)
  "minScale": 0.5,     // Minimum zoom level (0.5x = zoomed out to see twice as much)
  "maxScale": 10.0,    // Maximum zoom level (10x = zoomed in to see 10x detail)
  "wheelEnabled": true // Enable mouse wheel zooming
},
"scroll": {
  "keyStep": 0.1,      // Keyboard navigation step size (proportion of visible area)
  "smoothScroll": true // Enable smooth scrolling animation
}
```

## Implementation Plan

1. Add zoom configuration to config.json
2. Implement zoom methods in PyQtGraphWaveformView class
3. Update scroll bar functionality to sync with view changes
4. Connect zoom buttons to new implementation
5. Add keyboard and mouse wheel navigation
6. Create tests to verify zoom and scroll behavior
7. Update documentation

## Testing Strategy

We'll create tests to verify:
- Zoom operations respect bounds (0.5x to 10x)
- Zoom preserves view context (center point)
- Scroll bar accurately reflects view state
- Keyboard and mouse navigation work as expected
- Configuration options are applied correctly

## Benefits

The improved zoom and scroll functionality will:
- Provide a more intuitive user experience
- Make navigating through audio files easier
- Better leverage the capabilities of PyQtGraph
- Be highly configurable for different use cases
- Improve overall usability of the RCY application