"""Visual marker rendering for waveform view.

This module handles the visual presentation of marker handles (L/R locator boxes)
at the start and end marker positions, styled like professional audio software.

L (start) marker: Box with "L" text, positioned to the RIGHT of the marker line
R (end) marker: Box with "R" text, positioned to the LEFT of the marker line

Uses a custom DraggableHandle class for proper click and drag handling.
"""
from typing import Any, Callable, Optional
import numpy as np
from PyQt6.QtGui import QColor, QFont, QPainterPath, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QObject
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem
import pyqtgraph as pg
from config_manager import config
import logging

logger = logging.getLogger(__name__)


class DraggableHandle(QGraphicsRectItem):
    """A draggable handle box for marker manipulation.

    This custom QGraphicsRectItem handles mouse press/move/release events
    to provide smooth dragging of the associated marker.
    """

    def __init__(self, marker_type: str, color: QColor, callback: Optional[Callable] = None):
        """Initialize the draggable handle.

        Args:
            marker_type: 'start' or 'end'
            color: Fill color for the handle
            callback: Function to call during drag with (marker_type, new_x_position)
        """
        super().__init__()
        self.marker_type = marker_type
        self.callback = callback
        self._dragging = False

        # Set appearance
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setZValue(60)

        # Enable mouse tracking
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    def mousePressEvent(self, event):
        """Handle mouse press - start dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            event.accept()
            logger.debug("Handle %s: drag started", self.marker_type)
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        """Handle mouse move - update marker position."""
        if self._dragging and self.callback:
            # Get position in scene coordinates, then convert to view coordinates
            scene_pos = event.scenePos()
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view:
                # Get the plot's view box to convert to data coordinates
                # The callback will handle the actual position update
                self.callback(self.marker_type, scene_pos)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        """Handle mouse release - stop dragging."""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            logger.debug("Handle %s: drag finished", self.marker_type)
            # Notify callback that drag is finished (pass None for scene_pos)
            if self.callback:
                self.callback(self.marker_type, None)
            event.accept()
        else:
            event.ignore()

    def is_dragging(self) -> bool:
        """Check if this handle is currently being dragged."""
        return self._dragging


def update_marker_handle(
    widget: Any,
    marker_type: str,
    time_data: np.ndarray | None,
    active_plot: Any,
    start_marker: Any,
    end_marker: Any,
    stereo_display: bool,
    marker_handles: dict[str, Any],
    total_time: Optional[float] = None,
    on_handle_clicked: Optional[Callable] = None
) -> None:
    """Update visual marker handle box with L/R label.

    Creates or updates a box marker handle with L or R text label at the
    specified marker position. Uses pxMode=True for consistent pixel sizing
    regardless of zoom level or display mode.

    L (start) marker: Box to the right of marker with "L" text
    R (end) marker: Box to the left of marker with "R" text

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
        on_handle_clicked: Callback function called when handle is clicked,
                          receives (marker_type, event) as arguments
    """
    # Make sure we have valid time data
    if time_data is None:
        return

    try:
        if len(time_data) == 0:
            return
    except TypeError:
        return

    # Get marker reference
    if marker_type == 'start':
        marker = start_marker
        color = config.get_qt_color('startMarker')
        label_text = "L"
    else:
        marker = end_marker
        color = config.get_qt_color('endMarker')
        label_text = "R"

    # Ensure marker exists
    if marker is None:
        return

    try:
        position = marker.value()
        if position is None:
            return
    except Exception:
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
            _remove_handle(marker_type, marker_handles, active_plot)
            return
        # Clamp position to visible range for file boundary markers
        if is_at_file_start:
            position = min_pos
        elif is_at_file_end:
            position = max_pos

    # Ensure active plot exists
    if active_plot is None:
        return

    # Check if handle is currently being dragged - if so, don't recreate it
    handle_key = f"{marker_type}_handle"
    existing_handle = marker_handles.get(handle_key)
    if existing_handle is not None and hasattr(existing_handle, 'is_dragging') and existing_handle.is_dragging():
        logger.debug("Handle %s is being dragged, skipping recreation", marker_type)
        return

    # Remove old handle and text if exists
    _remove_handle(marker_type, marker_handles, active_plot)

    # Get the view box for coordinate info
    view_box = active_plot.getViewBox()
    if view_box is None:
        return

    # Get current view range
    try:
        y_range = view_box.viewRange()[1]
        y_min, y_max = y_range
    except Exception:
        return

    # Get UI configuration for marker size in pixels (FIXED size)
    box_size_px = config.get_ui_setting("markerHandles", "width", 14)

    # Calculate scales for positioning
    view_width = view_box.width()
    view_height = view_box.height()
    if view_width <= 0 or view_height <= 0:
        return

    x_range = view_box.viewRange()[0]
    x_min, x_max = x_range
    x_scale = (x_max - x_min) / view_width  # data units per pixel
    y_scale = (y_max - y_min) / view_height  # data units per pixel

    # Offset to position box beside marker line
    box_offset_x = x_scale * (box_size_px / 2 + 2)

    # Offset to keep box INSIDE the view (not at edge)
    # Position box center at y_min + half the box height in data units
    box_offset_y = y_scale * (box_size_px / 2 + 4)  # Extra padding from edge

    # Position box beside the marker line
    if marker_type == 'start':
        box_x = position + box_offset_x  # Box to the RIGHT of L marker
    else:
        box_x = position - box_offset_x  # Box to the LEFT of R marker

    box_y = y_min + box_offset_y  # Position ABOVE the bottom edge

    # Calculate box dimensions in data coordinates
    box_width_data = x_scale * box_size_px
    box_height_data = y_scale * box_size_px

    # Create draggable handle with callback
    handle = DraggableHandle(marker_type, QColor(color), on_handle_clicked)

    # Set rect in data coordinates (centered on box_x, box_y)
    handle.setRect(QRectF(
        box_x - box_width_data / 2,
        box_y - box_height_data / 2,
        box_width_data,
        box_height_data
    ))

    # Create text label (L or R) - TextItem already uses pixel coordinates
    text_item = pg.TextItem(
        text=label_text,
        color=QColor(config.get_qt_color('background')),
        anchor=(0.5, 0.5)
    )
    text_item.setPos(box_x, box_y)
    text_item.setZValue(61)

    # Set font
    font = QFont()
    font.setPointSize(8)
    font.setBold(True)
    text_item.setFont(font)

    # Add to plot - DraggableHandle is a QGraphicsItem so addItem works
    active_plot.addItem(handle)
    active_plot.addItem(text_item)

    handle_key = f"{marker_type}_handle"
    text_key = f"{marker_type}_text"
    marker_handles[handle_key] = handle
    marker_handles[text_key] = text_item


def _remove_handle(marker_type: str, marker_handles: dict[str, Any], active_plot: Any) -> None:
    """Remove existing handle and text items."""
    handle_key = f"{marker_type}_handle"
    text_key = f"{marker_type}_text"

    if handle_key in marker_handles:
        handle = marker_handles[handle_key]
        if handle is not None and active_plot is not None:
            try:
                if handle in active_plot.items:
                    active_plot.removeItem(handle)
            except Exception:
                pass
        marker_handles[handle_key] = None

    if text_key in marker_handles:
        text_item = marker_handles[text_key]
        if text_item is not None and active_plot is not None:
            try:
                if text_item in active_plot.items:
                    active_plot.removeItem(text_item)
            except Exception:
                pass
        marker_handles[text_key] = None


def is_click_on_handle(
    marker_handles: dict[str, Any],
    click_x: float,
    click_y: float,
    y_min: float,
    height_in_data: float
) -> str | None:
    """Check if a click position is within a marker handle's bounds.

    Args:
        marker_handles: Dictionary storing marker handle references
        click_x: X position of click in data coordinates
        click_y: Y position of click in data coordinates
        y_min: Bottom y coordinate of the view
        height_in_data: Height of handle in data units

    Returns:
        'start' if click is on L handle, 'end' if click is on R handle, None otherwise
    """
    for marker_type in ['start', 'end']:
        bounds_key = f"{marker_type}_bounds"
        if bounds_key in marker_handles and marker_handles[bounds_key] is not None:
            x_left, x_right = marker_handles[bounds_key]
            # Check if click is within x bounds
            if x_left <= click_x <= x_right:
                # Check if click is within y bounds (bottom of view)
                if y_min <= click_y <= y_min + height_in_data:
                    return marker_type
    return None


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
    try:
        if time_data is None:
            logger.debug("Can't clamp markers: No time data")
            return

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

        max_pos = time_data[-1]
        end_pos = end_marker.value()

        if end_pos > max_pos:
            logger.debug("Fixing end marker: %s -> %s", end_pos, max_pos)
            old_state = end_marker.blockSignals(True)
            end_marker.setValue(max_pos)
            end_marker.blockSignals(old_state)

            if stereo_display:
                if end_marker_right is not None:
                    old_state = end_marker_right.blockSignals(True)
                    end_marker_right.setValue(max_pos)
                    end_marker_right.blockSignals(old_state)

            _remove_handle('end', marker_handles, active_plot)
            update_marker_handle_func('end')
    except Exception as e:
        logger.debug("Error clamping markers: error=%s", e)
        return
