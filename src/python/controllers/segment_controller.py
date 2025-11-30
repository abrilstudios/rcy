"""Segment manipulation controller for RCY application."""

from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal
from enums import SplitMethod
import logging

logger = logging.getLogger(__name__)


class SegmentController(QObject):
    """Handles segment creation, removal, and audio splitting operations."""

    segments_changed = pyqtSignal(list)
    segments_updated = pyqtSignal()  # Signal to trigger view update

    def __init__(self, model: Any, view: Any) -> None:
        """Initialize SegmentController.

        Args:
            model: The audio processor model containing segment data
            view: The view instance for displaying segments
        """
        super().__init__()
        self.model = model
        self.view = view
        self.measure_resolution: int = 4

    def add_segment(self, click_time: float) -> None:
        """Add a new segment at the specified time position.

        Args:
            click_time: Time position (in seconds) where the segment should be added
        """
        self.model.add_segment(click_time)
        self.segments_updated.emit()

    def remove_segment(self, click_time: float) -> None:
        """Remove the segment at the specified time position.

        Args:
            click_time: Time position (in seconds) of the segment to remove
        """
        logger.debug("Removing segment at click_time: %s", click_time)
        try:
            self.model.remove_segment(click_time)
            logger.debug("Successfully called model.remove_segment")
        except Exception as e:
            logger.warning("Error in model.remove_segment: %s", e)
        self.segments_updated.emit()

    def split_audio(self, method: str | SplitMethod = SplitMethod.MEASURES,
                   measure_resolution: int | None = None,
                   num_measures: int | None = None,
                   threshold: float | None = None) -> None:
        """Split audio into segments using the specified method.

        Args:
            method: Split method - either 'measures' or 'transients'
            measure_resolution: Resolution for measure-based splits (bars per measure)
            num_measures: Number of measures in the audio (for measure-based splits)
            threshold: Detection threshold for transient-based splits

        Raises:
            ValueError: If an invalid split method is specified
        """
        # Convert string to enum if necessary
        if isinstance(method, str):
            method = SplitMethod(method)

        match method:
            case SplitMethod.MEASURES:
                resolution = measure_resolution if measure_resolution is not None else self.measure_resolution
                # Get marker positions from view to determine split region
                start_pos, end_pos = self.view.waveform_view.get_marker_positions()
                # Use marker region if markers have been moved from defaults
                if (start_pos is not None and end_pos is not None and
                    not (start_pos == 0 and abs(end_pos - self.model.total_time) < 0.01)):
                    logger.debug("Split by measures using marker region: %ss to %ss", start_pos, end_pos)
                    slices = self.model.split_by_measures(num_measures or 1, resolution, start_pos, end_pos)
                else:
                    logger.debug("Split by measures using full file duration")
                    slices = self.model.split_by_measures(num_measures or 1, resolution)
            case SplitMethod.TRANSIENTS:
                if threshold is None:
                    raise ValueError("threshold parameter required for transient split method")
                slices = self.model.split_by_transients(threshold=threshold)
            case _:
                raise ValueError(f"Invalid split method: {method}")
        self.view.update_slices(slices)

    def set_measure_resolution(self, resolution: int) -> None:
        """Set the measure resolution without automatically triggering a split.

        Args:
            resolution: Number of bars per measure for segment division
        """
        self.measure_resolution = resolution
