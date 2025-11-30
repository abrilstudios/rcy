"""
Plot rendering module for waveform visualization.

This module handles the core waveform plot updates including data rendering,
marker clamping, and handle updates.
"""
from typing import Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


def update_plot(
    widget: Any,
    time: np.ndarray,
    data_left: np.ndarray,
    data_right: np.ndarray | None = None,
    is_stereo: bool = False
) -> None:
    """Update waveform plot with new audio data.

    This function updates the waveform visualization with new audio data,
    handles stereo/mono display modes, clamps markers to valid data bounds,
    and updates marker handles.

    Args:
        widget: The PyQtGraphWaveformView widget instance
        time: Time axis array (x-axis data)
        data_left: Left channel (or mono) audio data (y-axis data)
        data_right: Right channel audio data for stereo files (optional)
        is_stereo: Whether the audio file is stereo (based on actual file metadata)

    Notes:
        - Marker positions are clamped to ensure they stay within data bounds
        - Marker handles are updated after data changes
        - Stereo display mode may differ from config; warnings are logged
    """
    logger.debug("\n==== WAVEFORM_VIEW UPDATE_PLOT ====")
    logger.debug("Updating plot with stereo=%s", is_stereo)

    # Detect if we need to rebuild the view for different stereo mode
    actual_stereo_display = is_stereo  # Use actual file metadata instead of config
    if actual_stereo_display != widget.stereo_display:
        logger.warning("Stereo mode changed: %s -> %s", widget.stereo_display, actual_stereo_display)
        logger.debug("Note: This would require rebuilding the view, which is complex.")
        logger.debug("For now, showing stereo layout but will be fixed in single plot architecture.")

    # Get detailed information about the current state
    old_start_pos = widget.start_marker.value() if widget.start_marker else None
    old_end_pos = widget.end_marker.value() if widget.end_marker else None
    try:
        old_max_pos = widget.time_data[-1] if widget.time_data is not None and len(widget.time_data) > 0 else None
    except TypeError:
        old_max_pos = None
    old_total_time = getattr(widget, 'total_time', None)

    # Check for existing handles
    old_start_handle = widget.marker_handles.get('start_handle')
    old_end_handle = widget.marker_handles.get('end_handle')

    # Save reference to time data
    try:
        if time is not None and len(time) > 0:
            new_max_pos = time[-1]
        else:
            new_max_pos = None
    except TypeError:
        new_max_pos = None

    widget.time_data = time
    if time is not None and len(time) > 0:
        logger.debug("update_plot: time array: len=%s, first=%s, last=%s",
                    len(time), time[0], time[-1])

    # Detail all current properties

    # Precheck - would end marker need clamping?
    if old_end_pos is not None and new_max_pos is not None and old_end_pos > new_max_pos:
        logger.debug("End marker position %s (stereo_display=%s, actual=%s) is beyond new max (%s) - will need clamping",
                    old_end_pos, widget.stereo_display, actual_stereo_display, new_max_pos)

    # Update left channel
    widget.waveform_left.setData(time, data_left)

    # Set view ranges for left channel
    # No padding to eliminate visual gap at marker end
    padding_value = 0.0  # No padding
    widget.plot_left.setXRange(time[0], time[-1], padding=padding_value)
    y_max_left = max(abs(data_left.min()), abs(data_left.max()))
    widget.plot_left.setYRange(-y_max_left, y_max_left, padding=0.1)

    # Update right channel if actually stereo (use file metadata, not config)
    if is_stereo and data_right is not None and widget.waveform_right is not None:
        widget.waveform_right.setData(time, data_right)

        # Set view ranges for right channel with padding
        widget.plot_right.setXRange(time[0], time[-1], padding=padding_value)
        y_max_right = max(abs(data_right.min()), abs(data_right.max()))
        widget.plot_right.setYRange(-y_max_right, y_max_right, padding=0.1)

        # Show right channel plot for stereo files
        if widget.plot_right is not None:
            widget.plot_right.setVisible(True)
    else:
        # Hide right channel plot for mono files
        if widget.plot_right is not None:
            widget.plot_right.setVisible(False)

    # Get marker positions immediately after data update but before clamping
    current_start_pos = widget.start_marker.value()
    current_end_pos = widget.end_marker.value()

    if current_end_pos > new_max_pos:
        logger.debug("Detected end marker (%s) beyond data bounds (%s)", current_end_pos, new_max_pos)

    # Check marker handle positions before clamping
    curr_start_handle = widget.marker_handles.get('start_handle')
    curr_end_handle = widget.marker_handles.get('end_handle')

    # Clamp marker positions to valid range after waveform change
    widget._clamp_markers_to_data_bounds()

    # Get marker positions after clamping
    new_start_pos = widget.start_marker.value()
    new_end_pos = widget.end_marker.value()

    # Verify clamping worked correctly
    if new_max_pos is not None and new_end_pos > new_max_pos:
        logger.debug("End marker %s (was %s) still beyond max (%s) after clamping!", new_end_pos, current_end_pos, new_max_pos)
    else:
        logger.debug("End marker position after clamping: %s", new_end_pos)

    # Check marker handles after clamping
    post_start_handle = widget.marker_handles.get('start_handle')
    post_end_handle = widget.marker_handles.get('end_handle')

    # Update marker handles
    widget._update_marker_handle('start')
    widget._update_marker_handle('end')

    # Final check on handles
    final_start_handle = widget.marker_handles.get('start_handle')
    final_end_handle = widget.marker_handles.get('end_handle')

    # Print final marker locations
    final_start_pos = widget.start_marker.value()
    final_end_pos = widget.end_marker.value()
    logger.debug("Final marker positions: start=%s, end=%s", final_start_pos, final_end_pos)
