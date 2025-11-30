"""TempoController: Handles BPM calculations, measure management, and marker-based tempo.

This controller manages all tempo-related functionality including:
- BPM calculation from measures
- Marker-based tempo detection
- Measure resolution management
- Tempo change notifications
"""

from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal
import logging

logger = logging.getLogger(__name__)


class TempoController(QObject):
    """Handles BPM calculations, measure management, and marker-based tempo.

    This controller is responsible for:
    - Calculating tempo from measure count
    - Updating tempo based on marker positions
    - Managing measure resolution settings
    - Coordinating with the model's source_bpm and playback tempo
    - Emitting signals when tempo or measures change

    Attributes:
        tempo: Current tempo in BPM
        num_measures: Number of measures in the current audio
        measure_resolution: Beat resolution (e.g., 4 for quarter notes, 8 for eighth notes)
        start_marker_pos: Position of start marker in seconds (None if not set)
        end_marker_pos: Position of end marker in seconds (None if not set)
        playback_tempo_enabled: Whether playback tempo adjustment is enabled (shared state)
        target_bpm: Target BPM for playback tempo adjustment (shared state)
    """

    # Signals
    tempo_changed = pyqtSignal(float, float)  # old_bpm, new_bpm
    measures_changed = pyqtSignal(int)  # new_count

    def __init__(self, model: Any, view: Any) -> None:
        """Initialize the TempoController.

        Args:
            model: The audio model (WavAudioProcessor) that provides tempo calculation
            view: The view component for updating UI elements
        """
        super().__init__()
        self.model = model
        self.view = view

        # State owned by this controller
        self.tempo: float = 120.0
        self.num_measures: int = 1
        self.measure_resolution: int = 4
        self.start_marker_pos: float | None = None
        self.end_marker_pos: float | None = None

        # Shared state (will be set by coordinator)
        self.playback_tempo_enabled: bool = False
        self.target_bpm: int = 120

    def get_tempo(self) -> float:
        """Get the current tempo in BPM.

        Returns:
            The current tempo value in beats per minute
        """
        return self.tempo

    def on_measures_changed(self, num_measures: int) -> None:
        """Handle measure count change and recalculate tempo.

        This method:
        1. Updates the measure count
        2. Recalculates tempo from the model
        3. Updates model's source_bpm to match new tempo
        4. Updates target_bpm to match new tempo (usability choice)
        5. Updates playback tempo settings if enabled
        6. Updates UI displays

        Args:
            num_measures: The new number of measures
        """
        logger.debug("\n===== (on_measures_changed) DETAILED TEMPO UPDATE FROM MEASURES CHANGE =====")

        # Store old values for debugging
        old_measures = self.num_measures
        old_tempo = self.tempo
        old_target_bpm = self.target_bpm
        old_enabled = self.playback_tempo_enabled
        old_source_bpm = self.model.source_bpm

        logger.debug("Measure change detected:")
        logger.debug("     Current audio file: %s", self.model.filename)

        # Update measures and recalculate tempo
        self.num_measures = num_measures
        logger.debug("     Recalculating tempo with new measures...")

        # Use marker-based tempo if markers have been explicitly moved from defaults
        # This allows tempo adjustment based on the selected region
        if (self.start_marker_pos is not None and self.end_marker_pos is not None and
            not (self.start_marker_pos == 0 and abs(self.end_marker_pos - self.model.total_time) < 0.01)):
            # Markers have been moved, use marker span for tempo calculation
            logger.debug("     Using marker-based tempo calculation (markers at %s to %s)",
                        self.start_marker_pos, self.end_marker_pos)
            self._update_tempo_from_markers()
            # Don't proceed with rest of method since _update_tempo_from_markers handles everything
            logger.debug("===== END DETAILED TEMPO UPDATE FROM MEASURES CHANGE =====\n")
            self.measures_changed.emit(self.num_measures)
            return

        # Otherwise, use full file duration
        self.tempo = self.model.get_tempo(self.num_measures)
        logger.debug("     After measure change, tempo changed from %s to %s BPM", old_tempo, self.tempo)

        # CRITICAL FIX: Update model's source_bpm to match the new tempo
        # This ensures playback tempo adjustment works correctly
        self.model.source_bpm = self.tempo

        # Usability Choice: Update target BPM to match the new tempo
        self.target_bpm = int(round(self.tempo))
        logger.debug("     Target BPM updated from %s to %s", old_target_bpm, self.target_bpm)

        # Update the model's playback tempo settings if enabled
        if self.playback_tempo_enabled:
            logger.debug("     Calling model.set_playback_tempo(%s, %s)...", self.playback_tempo_enabled, self.target_bpm)
            ratio = self.model.set_playback_tempo(self.playback_tempo_enabled, self.target_bpm)
        else:
            logger.debug("     Not updating playback tempo settings (playback_tempo_enabled is False)")
            ratio = self.model.get_playback_ratio()

        # Update the main tempo display
        logger.debug("     Setting tempo display to %s BPM", self.tempo)
        self.view.update_tempo(self.tempo)

        # Update the playback tempo UI with the new settings
        if self.playback_tempo_enabled:
            self.view.update_playback_tempo_display(self.playback_tempo_enabled, self.target_bpm, ratio)
        else:
            logger.debug("     Not updating playback tempo UI (playback_tempo_enabled is False)")

        logger.debug("Final state:")
        logger.debug("- Measures: %s", self.num_measures)
        logger.debug("- Target BPM: %s", self.target_bpm)
        logger.debug("- Playback tempo enabled: %s", self.playback_tempo_enabled)
        logger.debug("===== END DETAILED TEMPO UPDATE FROM MEASURES CHANGE =====\n")

        # Emit signals
        self.tempo_changed.emit(old_tempo, self.tempo)
        self.measures_changed.emit(self.num_measures)

    def on_start_marker_changed(self, position: float) -> None:
        """Handle start marker position change.

        Updates the start marker position and recalculates tempo if both
        start and end markers are set.

        Args:
            position: New start marker position in seconds
        """
        self.start_marker_pos = position
        logger.debug("Start marker position updated: %s", position)

        # Update tempo if both markers are set
        if self.start_marker_pos is not None and self.end_marker_pos is not None:
            self._update_tempo_from_markers()

    def on_end_marker_changed(self, position: float) -> None:
        """Handle end marker position change.

        Updates the end marker position and recalculates tempo if both
        start and end markers are set.

        Args:
            position: New end marker position in seconds
        """
        self.end_marker_pos = position
        logger.debug("End marker position updated: %s", position)

        # Update tempo if both markers are set
        if self.start_marker_pos is not None and self.end_marker_pos is not None:
            self._update_tempo_from_markers()

    def _update_tempo_from_markers(self) -> None:
        """Calculate tempo based on the current marker positions.

        This method:
        1. Validates that markers are in correct order (start < end)
        2. Calculates duration between markers
        3. Calculates tempo based on measures and duration
        4. Updates target_bpm if playback tempo adjustment is enabled
        5. Updates model's source_bpm for consistent playback
        6. Updates model's playback tempo settings
        7. Updates UI displays

        The tempo is calculated using the formula:
        BPM = (num_measures * beats_per_measure) / (duration_in_minutes)

        Assumes 4/4 time signature (4 beats per measure).
        """
        logger.debug("Updating tempo from marker positions: start=%s, end=%s", self.start_marker_pos, self.end_marker_pos)

        # Skip if markers are invalid
        if self.start_marker_pos >= self.end_marker_pos:
            logger.debug("Markers invalid: start position >= end position")
            return

        # Calculate duration between markers
        duration = self.end_marker_pos - self.start_marker_pos

        # Calculate tempo based on the selected duration
        beats_per_measure = 4  # Assuming 4/4 time
        total_beats = self.num_measures * beats_per_measure
        total_time_minutes = duration / 60

        # Calculate tempo if time is valid
        if total_time_minutes > 0:
            # Store the old values for debugging
            old_tempo = self.tempo
            old_target_bpm = self.target_bpm
            old_enabled = self.playback_tempo_enabled

            # Calculate the new tempo
            self.tempo = total_beats / total_time_minutes

            # Update target BPM to match the new tempo, but only if tempo adjustment is already enabled
            # This preserves the user's choice about whether tempo adjustment is enabled
            if self.playback_tempo_enabled:
                self.target_bpm = int(round(self.tempo))

            # Update the model's source BPM
            # This ensures consistent playback when markers are moved
            old_source_bpm = self.model.source_bpm
            self.model.source_bpm = self.tempo
            logger.debug("DEBUG: Updated model.source_bpm from %s to %s BPM", old_source_bpm, self.tempo)
            logger.debug("DEBUG: - Duration between markers: %s seconds", duration)
            logger.debug("DEBUG: - New tempo: %s BPM", self.tempo)
            logger.debug("DEBUG: - New source BPM: %s", self.model.source_bpm)
            logger.debug("DEBUG: - New target BPM: %s", self.target_bpm)

            # Update the model's playback tempo settings directly
            # This preserves the user's choice about whether tempo adjustment is enabled
            self.model.set_playback_tempo(self.playback_tempo_enabled, self.target_bpm)

            # Update the main tempo display
            self.view.update_tempo(self.tempo)

            # Update the playback tempo display with the new settings
            ratio = self.model.get_playback_ratio()
            self.view.update_playback_tempo_display(
                self.playback_tempo_enabled,
                self.target_bpm,
                ratio
            )

            logger.debug("=== TEMPO UPDATED: %s BPM, Target=%s, Enabled=%s ===", self.tempo, self.target_bpm, self.playback_tempo_enabled)

            # Emit signal
            self.tempo_changed.emit(old_tempo, self.tempo)

    def set_measure_resolution(self, resolution: int) -> None:
        """Set the measure resolution without automatically triggering a split.

        The measure resolution determines how audio is split:
        - 4 = quarter notes
        - 8 = eighth notes
        - 16 = sixteenth notes

        Args:
            resolution: The new measure resolution value
        """
        self.measure_resolution = resolution
