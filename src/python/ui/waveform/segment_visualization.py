"""
Segment visualization module for waveform display.

This module handles rendering and management of segment markers,
highlights, and visual indicators for audio segments.
"""
from typing import Any
from PyQt6.QtGui import QColor, QBrush
import pyqtgraph as pg
import logging

from config_manager import config

logger = logging.getLogger(__name__)


def update_slices(
    widget: Any,
    slices: list[float],
    total_time: float | None = None
) -> None:
    """Render slice marker lines on plots.

    Updates the segment slice markers displayed on the waveform plots.
    Clears existing markers and renders new ones based on the provided slice positions.

    Args:
        widget: The PyQtGraphWaveformView widget instance
        slices: List of time positions (in seconds) where slices should be rendered
        total_time: Total duration of the audio (optional)

    Notes:
        - Clears all existing segment markers before rendering new ones
        - Updates marker positions and handles after rendering
        - Ensures markers stay within valid data bounds
    """
    # Record marker positions before update
    pre_start_pos = widget.start_marker.value()
    pre_end_pos = widget.end_marker.value()

    if total_time is not None:
        old_total_time = getattr(widget, 'total_time', None)
        widget.total_time = total_time

    # Save current slices
    widget.current_slices = slices

    # Get data boundaries with TypeError protection
    data_max = None
    try:
        if widget.time_data is not None and len(widget.time_data) > 0:
            data_max = widget.time_data[-1]
    except TypeError:
        logger.error("TypeError when getting data_max")

    # Ensure markers are within valid bounds
    try:
        if widget.time_data is not None and len(widget.time_data) > 0:
            widget._clamp_markers_to_data_bounds()
    except TypeError:
        logger.error("TypeError when clamping markers")

    # Get positions after clamping
    post_start_pos = widget.start_marker.value()
    post_end_pos = widget.end_marker.value()

    # Ensure start and end markers are sufficiently separated
    if abs(post_end_pos - post_start_pos) < 0.1:
        new_end_pos = widget.total_time
        widget.set_end_marker(new_end_pos)

    # Clear existing slice markers
    _clear_segment_markers(widget)

    # Add slice markers
    for plot in [widget.plot_left, widget.plot_right]:
        if plot is None:
            continue

        # Add new slice markers
        for slice_time in slices:
            line = pg.InfiniteLine(
                pos=slice_time,
                angle=90,
                movable=False,
                pen=widget._create_pen('sliceActive', width=1)
            )
            plot.addItem(line)

    # Get final marker positions after all updates
    final_start_pos = widget.start_marker.value()
    final_end_pos = widget.end_marker.value()

    # Update marker handles for both markers
    widget._update_marker_handle('start')
    widget._update_marker_handle('end')


def _clear_segment_markers(widget: Any) -> None:
    """Clear all segment markers from the plots.

    Removes all InfiniteLine items from the plots that represent segment
    markers, while preserving start/end markers.

    Args:
        widget: The PyQtGraphWaveformView widget instance

    Notes:
        - Only removes segment slice markers, not start/end markers
        - Operates on both left and right plots if in stereo mode
    """
    # For each plot
    for plot in [widget.plot_left, widget.plot_right]:
        if plot is None:
            continue

        # Get all items in the plot
        items = plot.items.copy()

        # Remove all InfiniteLine items that aren't start/end markers
        for item in items:
            if (isinstance(item, pg.InfiniteLine) and
                item not in [widget.start_marker_left, widget.end_marker_left,
                            widget.start_marker_right, widget.end_marker_right]):
                plot.removeItem(item)


def highlight_active_segment(
    widget: Any,
    start_time: float,
    end_time: float
) -> None:
    """Highlight the currently playing segment.

    Creates a visual highlight region between the specified start and end times
    on all active plots.

    Args:
        widget: The PyQtGraphWaveformView widget instance
        start_time: Start time of the segment in seconds
        end_time: End time of the segment in seconds

    Notes:
        - Clears any existing highlights before adding new one
        - Uses configured activeSegmentHighlight color with 25% opacity
        - Adds highlight to both left and right plots in stereo mode
    """
    # Clear any existing highlight
    clear_active_segment_highlight(widget)

    # Get highlight color
    color = QColor(config.get_qt_color('activeSegmentHighlight'))
    color.setAlpha(64)  # 25% opacity

    # Create brushes for filling
    brush = QBrush(color)

    # Create linear regions (highlighted spans)
    for plot in [widget.plot_left, widget.plot_right]:
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
        widget.active_segment_items.append(region)


def clear_active_segment_highlight(widget: Any) -> None:
    """Remove the active segment highlight.

    Clears all active segment highlight regions from the plots.

    Args:
        widget: The PyQtGraphWaveformView widget instance

    Notes:
        - Safely removes items only if they're still in a scene
        - Clears the internal tracking list after removal
    """
    # Remove all active segment highlights
    for item in widget.active_segment_items:
        if item.scene() is not None:  # Only remove if still in a scene
            item.scene().removeItem(item)

    # Clear the list
    widget.active_segment_items = []


def highlight_segment(
    widget: Any,
    start_time: float,
    end_time: float,
    temporary: bool = False
) -> None:
    """Highlight a segment of the waveform.

    Creates a visual highlight region for a segment. Can create either
    permanent (active) or temporary (selection) highlights with different colors.

    Args:
        widget: The PyQtGraphWaveformView widget instance
        start_time: Start time of the segment in seconds
        end_time: End time of the segment in seconds
        temporary: If True, uses selectionHighlight color; if False, uses
                  activeSegmentHighlight color

    Notes:
        - Temporary highlights use ~30% opacity, active highlights use 25% opacity
        - Non-temporary highlights clear existing highlights first
        - Adds highlight to both left and right plots in stereo mode
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
        clear_active_segment_highlight(widget)

    # Create linear regions (highlighted spans)
    for plot in [widget.plot_left, widget.plot_right]:
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
        widget.active_segment_items.append(region)
