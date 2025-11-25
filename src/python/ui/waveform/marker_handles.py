"""Visual marker rendering for waveform view.

This module handles the visual presentation of marker handles (rectangular
indicators) at the start and end marker positions.
"""
from typing import Any
import numpy as np
from PyQt6.QtGui import QColor
import pyqtgraph as pg
from config_manager import config
import logging

logger = logging.getLogger(__name__)


def update_marker_handle(
    widget: Any,
    marker_type: str,
    time_data: np.ndarray | None,
    active_plot: Any,
    start_marker: Any,
    end_marker: Any,
    stereo_display: bool,
    marker_handles: dict[str, Any],
    total_time: float | None = None
) -> None:
    """Update visual marker handle rectangles.

    Creates or updates a rectangular marker handle with a fixed pixel size at the
    specified marker position. The handle provides a visual indicator for the marker
    and is positioned at the bottom of the waveform view.

    Args:
        widget: The waveform view widget instance
        marker_type: Either 'start' or 'end'
        time_data: Array of time values for the waveform data
        active_plot: The active PyQtGraph plot widget
        start_marker: The start marker InfiniteLine
        end_marker: The end marker InfiniteLine
        stereo_display: Whether stereo display is enabled
        marker_handles: Dictionary storing marker handle references
        total_time: Total duration of audio file (for boundary detection)
    """
    # Make sure we have valid time data
    if time_data is None:
        return

    # Fix for TypeError: object of type 'NoneType' has no len()
    try:
        if len(time_data) == 0:
            return
    except TypeError:
        return

    # Get marker reference
    if marker_type == 'start':
        marker = start_marker
        color = config.get_qt_color('startMarker')
    else:
        marker = end_marker
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

    # Get valid data range (visible window)
    min_pos = time_data[0]
    max_pos = time_data[-1]

    # Check if marker is at file boundary (should always show handle)
    is_at_file_start = abs(position) < 0.001
    is_at_file_end = total_time is not None and abs(position - total_time) < 0.001

    # Guard clause: Don't draw handles for markers outside data range
    # UNLESS they are at file boundaries (0 or total_time)
    if position < min_pos or position > max_pos:
        if not is_at_file_start and not is_at_file_end:
            # Remove existing handle if there is one
            handle_key = f"{marker_type}_handle"
            if handle_key in marker_handles:
                handle = marker_handles[handle_key]
                if handle is not None and active_plot is not None and handle in active_plot.items:
                    active_plot.removeItem(handle)
                    marker_handles[handle_key] = None
            return
        # Clamp position to visible range for file boundary markers
        if is_at_file_start:
            position = min_pos
        elif is_at_file_end:
            position = max_pos

    # Ensure active plot exists
    if active_plot is None:
        return


    # Remove old handle if exists
    handle_key = f"{marker_type}_handle"
    if handle_key in marker_handles:
        handle = marker_handles[handle_key]
        if handle is not None and handle in active_plot.items:
            active_plot.removeItem(handle)

    # Get the view box for coordinate transformations
    view_box = active_plot.getViewBox()
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
    active_plot.addItem(handle)
    marker_handles[handle_key] = handle


def clamp_markers_to_data_bounds(
    time_data: np.ndarray | None,
    end_marker: Any,
    stereo_display: bool,
    end_marker_right: Any | None,
    marker_handles: dict[str, Any],
    active_plot: Any,
    update_marker_handle_func: callable
) -> None:
    """Ensure markers stay within valid data boundaries.

    Called after waveform updates to prevent markers from going outside the valid range,
    which would make their handles invisible or misplaced.

    Args:
        time_data: Array of time values for the waveform data
        end_marker: The end marker InfiniteLine
        stereo_display: Whether stereo display is enabled
        end_marker_right: The right channel end marker (if stereo)
        marker_handles: Dictionary storing marker handle references
        active_plot: The active PyQtGraph plot widget
        update_marker_handle_func: Function to call to update marker handle
    """
    # Simple version focusing on the core issue: end marker goes beyond data bounds
    try:
        # Make sure we have the essential components and valid data
        if time_data is None:
            logger.debug("Can't clamp markers: No time data")
            return

        # Fix for TypeError: object of type 'NoneType' has no len()
        try:
            if len(time_data) == 0:
                logger.debug("Can't clamp markers: Time data is empty")
                return
        except TypeError:
            logger.debug("Can't clamp markers: time_data is not iterable")
            return

        if end_marker is None:
            logger.debug("Can't clamp markers: No end marker")
            return

        # Get the max position from time_data
        max_pos = time_data[-1]

        # Get the end marker position
        end_pos = end_marker.value()

        # CRITICAL FIX: Force end marker to max_pos if beyond bounds
        if end_pos > max_pos:
            logger.debug("Fixing end marker: %s -> %s")
            # Block signals during update to prevent recursion
            old_state = end_marker.blockSignals(True)
            end_marker.setValue(max_pos)
            end_marker.blockSignals(old_state)

            # Also update stereo marker if present
            if stereo_display:
                if end_marker_right is not None:
                    old_state = end_marker_right.blockSignals(True)
                    end_marker_right.setValue(max_pos)
                    end_marker_right.blockSignals(old_state)

            # Update the marker handle
            if 'end_handle' in marker_handles and marker_handles['end_handle'] is not None:
                if active_plot is not None:
                    try:
                        active_plot.removeItem(marker_handles['end_handle'])
                    except:
                        pass
            update_marker_handle_func('end')
    except Exception as e:
        logger.debug("Error clamping markers: end_pos=%s, max_pos=%s, error=%s", end_pos, max_pos, e)
        # No matter what happens, don't crash - just return
        return
