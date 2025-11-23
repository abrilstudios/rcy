"""
Abstract base class for waveform visualization.

This module provides the BaseWaveformView class which defines the interface
for waveform visualization implementations in the RCY application.
All waveform views must inherit from this class and implement the abstract methods.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal
from typing import Optional, Tuple
import numpy as np

from config_manager import config
import logging

logger = logging.getLogger(__name__)


class BaseWaveformView(QWidget):
    """
    Abstract base class for waveform visualization.

    Defines the interface for waveform visualization implementations,
    including signal definitions and abstract method declarations.
    Subclasses must implement all abstract methods to provide specific
    visualization backends (e.g., PyQtGraph, Matplotlib).

    Attributes:
        dragging_marker: str | None
            Track which marker (if any) is currently being dragged
        current_slices: list[float]
            List of time positions for segment slices
        total_time: float
            Total duration of the audio in seconds
        snap_threshold: float
            Threshold distance (in seconds) for marker snapping behavior
        stereo_display: bool
            Whether to display stereo (2 channel) or mono (1 channel) view
    """

    # Signals
    marker_dragged = pyqtSignal(str, float)
    """
    Emitted when a marker is being dragged.

    Args:
        str: Marker type ('start' or 'end')
        float: Current position in seconds
    """

    marker_released = pyqtSignal(str, float)
    """
    Emitted when a marker drag operation completes.

    Args:
        str: Marker type ('start' or 'end')
        float: Final position in seconds
    """

    segment_clicked = pyqtSignal(float)
    """
    Emitted when the waveform is clicked without modifiers.

    Args:
        float: Click position in seconds
    """

    add_segment = pyqtSignal(float)
    """
    Emitted when a segment should be added (Ctrl+Click or Alt+Click).

    Args:
        float: Position where segment should be added in seconds
    """

    remove_segment = pyqtSignal(float)
    """
    Emitted when a segment should be removed (Ctrl+Alt+Click or Alt+Cmd+Click).

    Args:
        float: Position of segment to remove in seconds
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the base waveform view.

        Args:
            parent: Parent widget, defaults to None
        """
        super().__init__(parent)

        # Initialize marker tracking
        self.dragging_marker: Optional[str] = None

        # Initialize slice management
        self.current_slices: list[float] = []

        # Initialize time tracking
        self.total_time: float = 0

        # Initialize marker snapping
        self.snap_threshold: float = config.get_snap_threshold(0.025)

        # Initialize stereo/mono display mode
        # Using unified config accessor for stereo display setting
        self.stereo_display: bool = config.get_stereo_display(True)

    def update_plot(
        self,
        time: np.ndarray,
        data_left: np.ndarray,
        data_right: Optional[np.ndarray] = None,
        is_stereo: bool = False
    ) -> None:
        """
        Update the plot with new audio data.

        Called when audio data is loaded or changed. Must update the visual
        representation of the waveform based on the provided audio samples.

        Args:
            time: Time array in seconds (x-axis data)
            data_left: Left channel audio samples (y-axis data)
            data_right: Right channel audio samples, None for mono files
            is_stereo: Whether the audio file is stereo

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement update_plot")

    def update_slices(
        self,
        slices: list[float],
        total_time: Optional[float] = None
    ) -> None:
        """
        Update the segment slices displayed on the waveform.

        Called when segments are added, removed, or modified. Must update
        the visual markers representing segment boundaries.

        Args:
            slices: List of time positions (in seconds) where segments begin
            total_time: Total duration of the audio, None to keep current value

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement update_slices")

    def set_start_marker(self, position: float) -> None:
        """
        Set the position of the start marker.

        Updates the visual position of the start marker without emitting
        signals. This method is called programmatically to position markers
        without triggering controller updates.

        Args:
            position: Marker position in seconds

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement set_start_marker")

    def set_end_marker(self, position: float) -> None:
        """
        Set the position of the end marker.

        Updates the visual position of the end marker without emitting
        signals. This method is called programmatically to position markers
        without triggering controller updates.

        Args:
            position: Marker position in seconds

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement set_end_marker")

    def get_marker_positions(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Get the positions of both markers.

        Returns the current positions of the start and end markers.
        Used by the controller to query the current marker state.

        Returns:
            Tuple of (start_position, end_position) in seconds, or (None, None)
            if markers are not available

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement get_marker_positions")

    def set_view_range(
        self,
        x_min: float,
        x_max: float,
        y_min: Optional[float] = None,
        y_max: Optional[float] = None
    ) -> None:
        """
        Set the view range for the waveform display.

        Updates the visible area of the plot. This method allows external
        control over pan and zoom operations.

        Args:
            x_min: Minimum time value to display (in seconds)
            x_max: Maximum time value to display (in seconds)
            y_min: Minimum amplitude value to display, None for auto
            y_max: Maximum amplitude value to display, None for auto

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement set_view_range")
