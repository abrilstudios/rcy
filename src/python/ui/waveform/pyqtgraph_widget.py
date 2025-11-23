"""
PyQtGraph-based waveform visualization widget.

This module provides the concrete PyQtGraph implementation of the waveform
visualization, delegating specific functionality to specialized modules.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtGui import QColor, QPen
from typing import Any, Optional, Tuple
from config_manager import config
import pyqtgraph as pg
import numpy as np
import logging

from ui.waveform.base import BaseWaveformView
from ui.waveform import (
    marker_handles,
    marker_interactions,
    plot_rendering,
    segment_visualization,
    plot_interactions
)

logger = logging.getLogger(__name__)


class PyQtGraphWaveformView(BaseWaveformView):
    """PyQtGraph implementation of the waveform visualization.

    This class provides the concrete implementation of waveform visualization
    using PyQtGraph, delegating specialized functionality to dedicated modules:
    - marker_handles: Visual marker rendering
    - marker_interactions: Marker dragging and positioning
    - plot_rendering: Core waveform plot updates
    - segment_visualization: Segment markers and highlights
    - plot_interactions: Mouse and keyboard event handling
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the PyQtGraph waveform view.

        Sets up the PyQtGraph graphics layout, creates stereo or mono plots
        based on configuration, initializes markers, and connects signals.

        Args:
            parent: Parent widget, defaults to None
        """
        super().__init__(parent)

        # Enable antialiasing for smoother drawing
        try:
            pg.setConfigOptions(antialias=True)
        except Exception as e:
            logger.warning("Warning: Could not set PyQtGraph config options: %s", e)

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
            logger.debug("Failed to initialize PyQtGraph graphics layout: %s", e)
            raise

        # Configure plots based on stereo/mono setting
        if self.stereo_display:
            self._setup_stereo_plots()
        else:
            self._setup_mono_plot()

        # Connect signals for marker interaction
        self._connect_marker_signals()

        # Add the graphics layout widget to the main layout
        self.layout.addWidget(self.graphics_layout)

    def _setup_stereo_plots(self) -> None:
        """Set up two plots for stereo display."""
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

    def _setup_mono_plot(self) -> None:
        """Set up a single plot for mono display."""
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

    def _create_pen(self, color_key: str, width: int = 1) -> Any:
        """Create a pen with the specified color and width.

        Args:
            color_key: Configuration key for the color
            width: Pen width in pixels

        Returns:
            PyQtGraph pen object
        """
        color = QColor(config.get_qt_color(color_key))
        return pg.mkPen(color=color, width=width)

    def _connect_marker_signals(self) -> None:
        """Connect signals for marker interaction."""
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

    # ========================================================================
    # Marker Handle Methods - Delegate to marker_handles module
    # ========================================================================

    def _update_marker_handle(self, marker_type: str) -> None:
        """Update visual marker handle rectangles.

        Delegates to marker_handles.update_marker_handle().

        Args:
            marker_type: Either 'start' or 'end'
        """
        marker_handles.update_marker_handle(
            widget=self,
            marker_type=marker_type,
            time_data=self.time_data,
            active_plot=self.active_plot,
            start_marker=self.start_marker,
            end_marker=self.end_marker,
            stereo_display=self.stereo_display,
            marker_handles=self.marker_handles
        )

    def _clamp_markers_to_data_bounds(self) -> None:
        """Ensure markers stay within valid data boundaries.

        Delegates to marker_handles.clamp_markers_to_data_bounds().
        """
        marker_handles.clamp_markers_to_data_bounds(
            time_data=self.time_data,
            end_marker=self.end_marker,
            stereo_display=self.stereo_display,
            end_marker_right=self.end_marker_right,
            marker_handles=self.marker_handles,
            active_plot=self.active_plot,
            update_marker_handle_func=self._update_marker_handle
        )

    # ========================================================================
    # Marker Interaction Methods - Delegate to marker_interactions module
    # ========================================================================

    def _on_marker_dragged(self, marker_type: str) -> None:
        """Handle marker drag events.

        Delegates to marker_interactions.on_marker_dragged().

        Args:
            marker_type: Either 'start' or 'end'
        """
        if marker_type == 'start':
            marker = self.start_marker
            opposite_marker = self.end_marker
        else:
            marker = self.end_marker
            opposite_marker = self.start_marker

        marker_interactions.on_marker_dragged(
            marker_type=marker_type,
            marker=marker,
            opposite_marker=opposite_marker,
            time_data=self.time_data,
            total_time=self.total_time,
            stereo_display=self.stereo_display,
            stereo_markers=(self.start_marker_right, self.end_marker_right),
            update_marker_handle_func=self._update_marker_handle,
            marker_dragged_signal=self.marker_dragged
        )

    def _on_marker_drag_finished(self, marker_type: str) -> None:
        """Handle marker drag finished events.

        Delegates to marker_interactions.on_marker_drag_finished().

        Args:
            marker_type: Either 'start' or 'end'
        """
        if marker_type == 'start':
            marker = self.start_marker
        else:
            marker = self.end_marker

        marker_interactions.on_marker_drag_finished(
            marker_type=marker_type,
            marker=marker,
            clamp_markers_func=self._clamp_markers_to_data_bounds,
            update_marker_handle_func=self._update_marker_handle,
            marker_released_signal=self.marker_released
        )

    def set_start_marker(self, position: float) -> None:
        """Set the position of the start marker.

        Delegates to marker_interactions.set_start_marker().

        Args:
            position: Marker position in seconds
        """
        marker_interactions.set_start_marker(
            position=position,
            time_data=self.time_data,
            start_marker=self.start_marker,
            end_marker=self.end_marker,
            snap_threshold=self.snap_threshold,
            stereo_display=self.stereo_display,
            start_marker_right=self.start_marker_right,
            marker_handles=self.marker_handles,
            active_plot=self.active_plot,
            update_marker_handle_func=self._update_marker_handle
        )

    def set_end_marker(self, position: float) -> None:
        """Set the position of the end marker.

        Delegates to marker_interactions.set_end_marker().

        Args:
            position: Marker position in seconds
        """
        marker_interactions.set_end_marker(
            position=position,
            time_data=self.time_data,
            start_marker=self.start_marker,
            end_marker=self.end_marker,
            stereo_display=self.stereo_display,
            end_marker_right=self.end_marker_right,
            marker_handles=self.marker_handles,
            active_plot=self.active_plot,
            update_marker_handle_func=self._update_marker_handle
        )

    # ========================================================================
    # Plot Rendering Methods - Delegate to plot_rendering module
    # ========================================================================

    def update_plot(
        self,
        time: np.ndarray,
        data_left: np.ndarray,
        data_right: Optional[np.ndarray] = None,
        is_stereo: bool = False
    ) -> None:
        """Update the plot with new audio data.

        Delegates to plot_rendering.update_plot().

        Args:
            time: Time axis array (x-axis data)
            data_left: Left channel (or mono) audio data (y-axis data)
            data_right: Right channel audio data for stereo files (optional)
            is_stereo: Whether the audio file is stereo
        """
        plot_rendering.update_plot(
            widget=self,
            time=time,
            data_left=data_left,
            data_right=data_right,
            is_stereo=is_stereo
        )

    # ========================================================================
    # Segment Visualization Methods - Delegate to segment_visualization module
    # ========================================================================

    def update_slices(
        self,
        slices: list[float],
        total_time: Optional[float] = None
    ) -> None:
        """Update the segment slices displayed on the waveform.

        Delegates to segment_visualization.update_slices().

        Args:
            slices: List of time positions (in seconds) where slices should be rendered
            total_time: Total duration of the audio (optional)
        """
        segment_visualization.update_slices(
            widget=self,
            slices=slices,
            total_time=total_time
        )

    def highlight_active_segment(self, start_time: float, end_time: float) -> None:
        """Highlight the currently playing segment.

        Delegates to segment_visualization.highlight_active_segment().

        Args:
            start_time: Start time of the segment in seconds
            end_time: End time of the segment in seconds
        """
        segment_visualization.highlight_active_segment(
            widget=self,
            start_time=start_time,
            end_time=end_time
        )

    def clear_active_segment_highlight(self) -> None:
        """Remove the active segment highlight.

        Delegates to segment_visualization.clear_active_segment_highlight().
        """
        segment_visualization.clear_active_segment_highlight(widget=self)

    def highlight_segment(
        self,
        start_time: float,
        end_time: float,
        temporary: bool = False
    ) -> None:
        """Highlight a segment of the waveform.

        Delegates to segment_visualization.highlight_segment().

        Args:
            start_time: Start time of the segment in seconds
            end_time: End time of the segment in seconds
            temporary: If True, uses selectionHighlight color
        """
        segment_visualization.highlight_segment(
            widget=self,
            start_time=start_time,
            end_time=end_time,
            temporary=temporary
        )

    # ========================================================================
    # Plot Interaction Methods - Delegate to plot_interactions module
    # ========================================================================

    def _on_plot_clicked(self, event: Any) -> None:
        """Handle plot click events.

        Delegates to plot_interactions.on_plot_clicked() and emits appropriate signals.

        Args:
            event: PyQtGraph MouseClickEvent
        """
        result = plot_interactions.on_plot_clicked(
            widget=self,
            event=event,
            start_marker=self.start_marker,
            end_marker=self.end_marker,
            plot_left=self.plot_left,
            plot_right=self.plot_right
        )

        if result is not None:
            click_type, position = result

            if click_type == 'add_segment':
                try:
                    self.add_segment.emit(position)
                    logger.debug("Emitted add_segment signal at %f", position)
                except Exception as e:
                    logger.debug("Failed to emit add_segment signal at position %f: %s", position, e)
            elif click_type == 'remove_segment':
                try:
                    self.remove_segment.emit(position)
                    logger.debug("Emitted remove_segment signal at %f", position)
                except Exception as e:
                    logger.debug("Failed to emit remove_segment signal at position %f: %s", position, e)
            elif click_type == 'segment_clicked':
                self.segment_clicked.emit(position)

    # ========================================================================
    # Additional Helper Methods
    # ========================================================================

    def get_marker_positions(self) -> Tuple[Optional[float], Optional[float]]:
        """Get the positions of both markers.

        Returns:
            Tuple of (start_position, end_position) in seconds, or (None, None)
            if markers are not available
        """
        if not self.start_marker or not self.end_marker:
            return None, None

        start_val = self.start_marker.value()
        end_val = self.end_marker.value()
        logger.debug("get_marker_positions: start=%s, end=%s", start_val, end_val)
        return start_val, end_val

    def get_view_center(self) -> float:
        """Get the center position of the current view.

        Returns:
            Center position in seconds
        """
        if self.active_plot is None:
            return 0.0

        # Get the current view range
        x_min, x_max = self.active_plot.getViewBox().viewRange()[0]

        # Return the center position
        return (x_min + x_max) / 2.0

    def set_view_range(
        self,
        x_min: float,
        x_max: float,
        y_min: Optional[float] = None,
        y_max: Optional[float] = None
    ) -> None:
        """Set the view range for the waveform display.

        Args:
            x_min: Minimum time value to display (in seconds)
            x_max: Maximum time value to display (in seconds)
            y_min: Minimum amplitude value to display, None for auto
            y_max: Maximum amplitude value to display, None for auto
        """
        if self.active_plot is None:
            return

        # Set x-axis range
        self.active_plot.setXRange(x_min, x_max, padding=0)

        # Set y-axis range if specified
        if y_min is not None and y_max is not None:
            self.active_plot.setYRange(y_min, y_max, padding=0)


def create_waveform_view(parent: Optional[QWidget] = None) -> PyQtGraphWaveformView:
    """Create a PyQtGraph-based waveform view.

    Factory function for creating waveform view instances.

    Args:
        parent: Parent widget, defaults to None

    Returns:
        A new PyQtGraphWaveformView instance
    """
    return PyQtGraphWaveformView(parent)
