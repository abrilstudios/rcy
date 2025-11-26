"""Slice marker rendering with triangle indicators.

This module handles rendering downward-pointing triangles at the TOP
of the waveform view for slice/segment boundary markers.
"""
from typing import Any
import pyqtgraph as pg
from PyQt6.QtGui import QColor, QPainterPath
from config_manager import config
import logging

logger = logging.getLogger(__name__)


def create_downward_triangle_path() -> QPainterPath:
    """Create a downward-pointing triangle QPainterPath.

    Creates a triangle centered at (0,0) with width and height of 1.0
    for use with ScatterPlotItem. Points downward (toward waveform).

    Returns:
        QPainterPath: Triangle path pointing down
    """
    path = QPainterPath()
    # Triangle pointing DOWN: base at top, apex at bottom
    path.moveTo(-0.5, -0.5)   # Top-left
    path.lineTo(0.5, -0.5)    # Top-right
    path.lineTo(0.0, 0.5)     # Bottom apex (pointing down)
    path.closeSubpath()
    return path


def create_slice_markers(
    widget: Any,
    slices: list[float],
    plot: Any,
    total_time: float | None = None
) -> pg.ScatterPlotItem | None:
    """Create scatter plot item for slice triangles at top of waveform.

    Args:
        widget: The PyQtGraphWaveformView widget instance
        slices: List of time positions for slice markers (including start/end)
        plot: The PyQtGraph plot to add markers to
        total_time: Total audio duration (to filter out file boundaries)

    Returns:
        ScatterPlotItem with triangle markers, or None if no internal slices
    """
    if not slices:
        return None

    # Filter out file boundary slices (0 and total_time)
    # We only want triangles for internal slice markers
    internal_slices = []
    for slice_time in slices:
        is_at_start = abs(slice_time) < 0.001
        is_at_end = total_time is not None and abs(slice_time - total_time) < 0.001
        if not is_at_start and not is_at_end:
            internal_slices.append(slice_time)

    if not internal_slices:
        return None

    # Get view box for coordinate calculations
    view_box = plot.getViewBox()
    if view_box is None:
        return None

    y_range = view_box.viewRange()[1]
    y_max = y_range[1]  # Top of waveform

    # Get marker size from config (in pixels)
    marker_size_px = config.get_ui_setting("sliceMarkers", "width", 12)

    # Create triangle symbol
    triangle_path = create_downward_triangle_path()

    # Get slice color
    color = QColor(config.get_qt_color('sliceActive'))

    # Create y positions at the TOP of the view
    y_positions = [y_max] * len(internal_slices)

    scatter = pg.ScatterPlotItem(
        x=internal_slices,
        y=y_positions,
        symbol=triangle_path,
        size=marker_size_px,
        brush=color,
        pen=pg.mkPen(None),  # No border
        pxMode=True  # Size in pixels, not data units
    )
    scatter.setZValue(50)  # Above waveform

    return scatter


def update_slice_markers_position(
    scatter_item: pg.ScatterPlotItem | None,
    plot: Any
) -> None:
    """Update y-positions of slice markers to stay at top of view.

    Called when view range changes (zoom/scroll) to keep triangles
    anchored to the top of the visible waveform area.

    Args:
        scatter_item: The ScatterPlotItem containing slice triangles
        plot: The PyQtGraph plot containing the markers
    """
    if scatter_item is None:
        return

    view_box = plot.getViewBox()
    if view_box is None:
        return

    y_range = view_box.viewRange()[1]
    y_max = y_range[1]

    # Get current x positions from the scatter item's data
    data = scatter_item.data
    if data is None or len(data) == 0:
        return

    x_positions = [spot[0] for spot in data]
    y_positions = [y_max] * len(x_positions)

    scatter_item.setData(x=x_positions, y=y_positions)
