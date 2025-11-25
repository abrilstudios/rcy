"""Marker dragging and positioning interactions for waveform view.

This module handles all user interactions with markers including drag events,
positioning, and validation.
"""
from typing import Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


def on_marker_dragged(
    marker_type: str,
    marker: Any,
    opposite_marker: Any,
    time_data: np.ndarray | None,
    total_time: float,
    stereo_display: bool,
    stereo_markers: tuple[Any | None, Any | None] | None,
    update_marker_handle_func: callable,
    marker_dragged_signal: Any
) -> tuple[str, float]:
    """Handle marker drag event.

    Applies constraints to ensure markers stay within valid bounds and don't
    cross each other. Updates both mono and stereo markers if applicable.

    Args:
        marker_type: Either 'start' or 'end'
        marker: The marker being dragged
        opposite_marker: The other marker (end if dragging start, start if dragging end)
        time_data: Array of time values for the waveform data
        total_time: Total duration of the audio in seconds
        stereo_display: Whether stereo display is enabled
        stereo_markers: Tuple of (start_marker_right, end_marker_right) or None
        update_marker_handle_func: Function to call to update marker handle
        marker_dragged_signal: Signal to emit when marker is dragged

    Returns:
        Tuple of (marker_type, position) for the updated marker
    """
    if marker_type == 'start':
        # Get current marker position
        position = marker.value()

        # Apply constraints for valid start marker positions
        position = max(0.0, position)  # Never less than 0

        # Ensure start marker doesn't go beyond end marker
        end_pos = opposite_marker.value()
        position = min(position, end_pos - 0.01)

        # Apply position with constraints
        marker.setValue(position)

        # Update other markers in stereo mode
        if stereo_display and stereo_markers is not None:
            start_marker_right, _ = stereo_markers
            if start_marker_right is not None:
                start_marker_right.setValue(position)
    else:  # 'end'
        # Get current marker position
        position = marker.value()

        # Apply constraints for valid end marker positions
        position = max(0.0, position)  # Never less than 0
        if total_time > 0:
            position = min(position, total_time)  # Never beyond total_time

        # Ensure end marker doesn't go before start marker
        start_pos = opposite_marker.value()
        position = max(position, start_pos + 0.01)

        # Apply position with constraints
        marker.setValue(position)

        # Update other markers in stereo mode
        if stereo_display and stereo_markers is not None:
            _, end_marker_right = stereo_markers
            if end_marker_right is not None:
                end_marker_right.setValue(position)

    # Update marker handle
    update_marker_handle_func(marker_type)

    # Emit signal for controller
    logger.debug("Marker %s dragged to %ss")
    marker_dragged_signal.emit(marker_type, position)

    return (marker_type, position)


def on_marker_drag_finished(
    marker_type: str,
    marker: Any,
    clamp_markers_func: callable,
    update_marker_handle_func: callable,
    marker_released_signal: Any
) -> tuple[str, float]:
    """Handle marker drag finished event.

    Performs final validation and clamping of marker positions when drag is complete.

    Args:
        marker_type: Either 'start' or 'end'
        marker: The marker that finished dragging
        clamp_markers_func: Function to call to clamp markers to data bounds
        update_marker_handle_func: Function to call to update marker handle
        marker_released_signal: Signal to emit when marker is released

    Returns:
        Tuple of (marker_type, position) for the released marker
    """
    if marker_type == 'start':
        position = marker.value()
    else:  # 'end'
        position = marker.value()

    # Apply final marker bounds check
    clamp_markers_func()

    # Ensure both handles are updated
    update_marker_handle_func('start')
    update_marker_handle_func('end')

    # Emit signal for controller
    logger.debug("Marker %s released at position %s", marker_type, position)
    marker_released_signal.emit(marker_type, position)

    return (marker_type, position)


def set_start_marker(
    position: float,
    time_data: np.ndarray | None,
    start_marker: Any,
    end_marker: Any | None,
    snap_threshold: float,
    stereo_display: bool,
    start_marker_right: Any | None,
    marker_handles: dict[str, Any],
    active_plot: Any,
    update_marker_handle_func: callable
) -> float:
    """Set the position of the start marker.

    Validates and constrains the position to ensure it stays within valid bounds
    and maintains proper separation from the end marker.

    Args:
        position: Desired position in seconds
        time_data: Array of time values for the waveform data
        start_marker: The start marker InfiniteLine
        end_marker: The end marker InfiniteLine
        snap_threshold: Distance threshold for snapping to zero
        stereo_display: Whether stereo display is enabled
        start_marker_right: The right channel start marker (if stereo)
        marker_handles: Dictionary storing marker handle references
        active_plot: The active PyQtGraph plot widget
        update_marker_handle_func: Function to call to update marker handle

    Returns:
        The final position applied to the marker
    """
    # Always print the initial request for debugging

    # Apply snapping FIRST if close to the start (do this before bounds check)
    if position < snap_threshold:
        position = 0.0

    # Get valid data range from time_data
    if time_data is not None and len(time_data) > 0:
        data_min = time_data[0]
        data_max = time_data[-1]

        # Ensure position is within valid range
        # Special case: always allow 0.0 (file start) even if time_data doesn't start exactly at 0.0
        if position != 0.0 and position < data_min:
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
        start_marker.setValue(position)

        # Update stereo view if needed
        if stereo_display and start_marker_right is not None:
            start_marker_right.setValue(position)

        return position

    # Ensure start marker doesn't go beyond end marker
    if end_marker is not None:
        end_pos = end_marker.value()
        minimum_gap = 0.01  # Minimum 10ms gap between markers
        if position > end_pos - minimum_gap:
            position = max(0.0, end_pos - minimum_gap)

    # Block signals to prevent recursive callbacks
    old_block_state = start_marker.blockSignals(True)

    # Update marker with final position
    start_marker.setValue(position)

    # Restore signal state
    start_marker.blockSignals(old_block_state)

    # Update stereo view if needed
    if stereo_display and start_marker_right is not None:
        old_block_state = start_marker_right.blockSignals(True)
        start_marker_right.setValue(position)
        start_marker_right.blockSignals(old_block_state)


    # Remove old handle if it exists
    if 'start_handle' in marker_handles and marker_handles['start_handle'] is not None:
        active_plot.removeItem(marker_handles['start_handle'])
        marker_handles['start_handle'] = None

    # Always update the marker handle to reflect the new position
    update_marker_handle_func('start')

    return position


def set_end_marker(
    position: float,
    time_data: np.ndarray | None,
    start_marker: Any | None,
    end_marker: Any,
    stereo_display: bool,
    end_marker_right: Any | None,
    marker_handles: dict[str, Any],
    active_plot: Any,
    update_marker_handle_func: callable
) -> float:
    """Set the position of the end marker.

    Validates and constrains the position to ensure it stays within valid bounds
    and maintains proper separation from the start marker.

    Args:
        position: Desired position in seconds
        time_data: Array of time values for the waveform data
        start_marker: The start marker InfiniteLine
        end_marker: The end marker InfiniteLine
        stereo_display: Whether stereo display is enabled
        end_marker_right: The right channel end marker (if stereo)
        marker_handles: Dictionary storing marker handle references
        active_plot: The active PyQtGraph plot widget
        update_marker_handle_func: Function to call to update marker handle

    Returns:
        The final position applied to the marker
    """
    # Always print the initial request for debugging

    # Get valid data range from time_data
    if time_data is not None and len(time_data) > 0:
        data_min = time_data[0]
        data_max = time_data[-1]

        # CRITICAL FIX: ALWAYS enforce data bounds
        # This ensures the end marker is never beyond the available data
        if position > data_max:
            position = data_max
    else:
        # If we don't have time data, this is probably initialization
        # Just record the intended position and return
        # Still verify not negative
        position = max(0.0, position)
        end_marker.setValue(position)

        # Update stereo view if needed
        if stereo_display and end_marker_right is not None:
            end_marker_right.setValue(position)

        return position

    # Apply basic validation - never less than data_min (usually 0)
    position = max(data_min, position)

    # Ensure end marker doesn't go before start marker
    if start_marker is not None:
        start_pos = start_marker.value()
        minimum_gap = 0.01  # Minimum 10ms gap between markers
        if position < start_pos + minimum_gap:
            position = start_pos + minimum_gap

    # Block signals to prevent recursive callbacks
    old_block_state = end_marker.blockSignals(True)

    # Update marker with final position
    end_marker.setValue(position)

    # Restore signal state
    end_marker.blockSignals(old_block_state)

    # Update stereo view if needed
    if stereo_display and end_marker_right is not None:
        old_block_state = end_marker_right.blockSignals(True)
        end_marker_right.setValue(position)
        end_marker_right.blockSignals(old_block_state)


    # Remove old handle if it exists
    if 'end_handle' in marker_handles and marker_handles['end_handle'] is not None:
        active_plot.removeItem(marker_handles['end_handle'])
        marker_handles['end_handle'] = None

    # Always update the marker handle to reflect the new position
    update_marker_handle_func('end')

    return position
