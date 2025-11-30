"""Export controller for RCY application."""

from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal
from export_utils import ExportUtils
import logging

logger = logging.getLogger(__name__)


class ExportController(QObject):
    """Handles audio segment export operations."""

    export_complete = pyqtSignal(list)
    export_failed = pyqtSignal(str)

    def __init__(self, model: Any, view: Any) -> None:
        """Initialize ExportController.

        Args:
            model: The audio processor model containing segments
            view: The view instance for user feedback
        """
        super().__init__()
        self.model = model
        self.view = view
        self.tempo: float = 120.0
        self.num_measures: int = 1
        self.start_marker_pos: float | None = None
        self.end_marker_pos: float | None = None

    def export_segments(self, directory: str) -> list[str]:
        """Export audio segments to files.

        Exports each segment as a separate audio file to the specified directory.
        If no segments are defined, uses marker positions if available, otherwise
        exports the entire audio.

        Args:
            directory: Target directory path for exported files

        Returns:
            list[str]: List of exported file paths

        Raises:
            IOError: If export operation fails
        """
        logger.debug("Starting segment export to directory: %s", directory)
        try:
            exported_files = ExportUtils.export_segments(
                self.model,
                self.tempo,
                self.num_measures,
                directory,
                self.start_marker_pos,
                self.end_marker_pos
            )
            logger.debug("Successfully exported %d segments", len(exported_files))
            return exported_files
        except Exception as e:
            logger.warning("Failed to export segments: %s", e)
            raise

    def set_tempo(self, tempo: float) -> None:
        """Set the tempo for export calculations.

        Args:
            tempo: Tempo in BPM
        """
        self.tempo = tempo

    def set_num_measures(self, num_measures: int) -> None:
        """Set the number of measures for export calculations.

        Args:
            num_measures: Number of measures in the audio
        """
        self.num_measures = num_measures

    def set_marker_positions(self, start_pos: float | None, end_pos: float | None) -> None:
        """Set marker positions for export fallback.

        Args:
            start_pos: Start marker position in seconds (or None)
            end_pos: End marker position in seconds (or None)
        """
        self.start_marker_pos = start_pos
        self.end_marker_pos = end_pos
