"""Playback controller for managing audio playback, looping, and playback modes."""

from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal
from enums import PlaybackMode
import logging

logger = logging.getLogger(__name__)


class PlaybackController(QObject):
    """Handles playback control, looping, and playback modes.

    This controller manages all playback-related functionality including:
    - Playing audio segments at specific time positions
    - Handling playback modes (one-shot, loop, loop-reverse)
    - Managing segment boundaries and playback regions
    - Coordinating playback state between model and view

    Signals:
        playback_started: Emitted when playback begins (start_time, end_time)
        playback_stopped: Emitted when playback stops
        playback_mode_changed: Emitted when playback mode changes (mode)
    """

    # Signals
    playback_started = pyqtSignal(float, float)  # start, end
    playback_stopped = pyqtSignal()
    playback_mode_changed = pyqtSignal(str)  # mode

    def __init__(self, model: Any, view: Any) -> None:
        """Initialize the playback controller.

        Args:
            model: The audio processor model
            view: The view component for UI updates
        """
        super().__init__()
        self.model = model
        self.view = view

        # Playback state
        self.playback_mode: PlaybackMode = PlaybackMode.ONE_SHOT
        self.is_playing_reverse: bool = False
        self.current_segment: tuple[float | None, float | None] = (None, None)
        self.current_slices: list[float] = []

        logger.debug("PlaybackController initialized with mode: %s", self.playback_mode)

    def set_playback_mode(self, mode: str | PlaybackMode) -> bool:
        """Set the playback mode.

        Args:
            mode: One of 'one-shot', 'loop', or 'loop-reverse' (string or PlaybackMode enum)

        Returns:
            True if mode was valid and set successfully, False otherwise
        """
        # Convert string to enum if necessary
        if isinstance(mode, str):
            try:
                mode = PlaybackMode(mode)
            except ValueError:
                logger.debug("Invalid playback mode: %s (must be one of: %s)", mode, list(PlaybackMode))
                return False

        # Only update if different
        if mode != self.playback_mode:
            logger.debug("Playback mode changed from '%s' to '%s'", self.playback_mode, mode)
            self.playback_mode = mode

            # Update playback mode in audio engine
            self.model.audio_engine.set_playback_mode(mode)

            # Update playback mode in view
            self.view.update_playback_mode_menu(mode.value)

            # Emit signal
            self.playback_mode_changed.emit(mode.value)

        return True

    def get_playback_mode(self) -> str:
        """Get the current playback mode.

        Returns:
            Current playback mode string
        """
        return self.playback_mode

    def play_segment(self, click_time: float) -> None:
        """Play or stop a segment based on click location.

        If playback is already in progress, stops playback. Otherwise,
        determines segment boundaries from the click position and starts
        playback according to the current playback mode.

        Args:
            click_time: Time position in seconds where the click occurred
        """
        logger.debug("Playback mode: %s", self.playback_mode)

        # Check both if the model is actively playing and if we're in a loop cycle
        if self.model.is_playing:
            logger.debug("### Already playing, stopping playback")
            self.stop_playback()
            # Clear current segment to prevent further looping
            self.current_segment = (None, None)
            return

        # If not playing, determine segment boundaries and play
        logger.debug("### Getting segment boundaries for click_time: %s", click_time)
        start, end = self.get_segment_boundaries(click_time)

        if start is not None and end is not None:
            logger.debug("### Playing segment: %ss to %ss, mode: %s", start, end, self.playback_mode)

            # Store current segment for looping
            self.current_segment = (start, end)
            self.is_playing_reverse = False

            # Highlight the active segment in the view
            self.view.highlight_active_segment(start, end)

            # Play the segment
            result = self.model.play_segment(start, end, reverse=False)
            logger.debug("Segment play result: %s", result)

            # Emit signal
            self.playback_started.emit(start, end)

    def stop_playback(self) -> None:
        """Stop any currently playing audio.

        Stops the audio engine and clears any active segment highlighting.
        Also resets the current segment state to prevent loop continuation.
        """
        self.model.stop_playback()

        # Clear the current_segment to prevent loop continuation
        if self.playback_mode in (PlaybackMode.LOOP, PlaybackMode.LOOP_REVERSE):
            self.current_segment = (None, None)

        # Clear the active segment highlight
        self.view.clear_active_segment_highlight()

        # Emit signal
        self.playback_stopped.emit()

    def play_selected_region(self) -> None:
        """Play or stop the audio between start and end markers.

        If playback is in progress, stops it. Otherwise, plays the region
        defined by the start and end markers according to the current
        playback mode.
        """
        # If already playing, stop playback
        if self.model.is_playing:
            self.stop_playback()
            return

        # If not playing, play the selected region
        start_marker_pos = getattr(self.view, 'start_marker_pos', None)
        end_marker_pos = getattr(self.view, 'end_marker_pos', None)

        # Try to get from controller if not found in view
        if start_marker_pos is None or end_marker_pos is None:
            # Access controller to get marker positions
            # This is a temporary workaround - ideally markers would be managed by a separate controller
            return

        if start_marker_pos is not None and end_marker_pos is not None:
            # Get tempo for logging (from controller state)
            tempo = getattr(self, '_tempo', 120)  # Default if not accessible
            target_bpm = getattr(self, '_target_bpm', 120)
            playback_tempo_enabled = getattr(self, '_playback_tempo_enabled', False)

            # Store current segment for looping
            self.current_segment = (start_marker_pos, end_marker_pos)
            self.is_playing_reverse = False

            logger.debug("Playing selected region: %s to %s (tempo=%s, target=%s, enabled=%s)",
                        start_marker_pos, end_marker_pos, tempo, target_bpm, playback_tempo_enabled)

            # Highlight the active segment in the view
            self.view.highlight_active_segment(start_marker_pos, end_marker_pos)

            self.model.play_segment(start_marker_pos, end_marker_pos)

            # Emit signal
            self.playback_started.emit(start_marker_pos, end_marker_pos)

    def get_segment_boundaries(self, click_time: float) -> tuple[float, float]:
        """Get the start and end times for the segment containing the click.

        Determines which segment contains the given time position based on
        the current slice markers. Handles special cases for first and last
        segments, and returns the full audio range if no segments are defined.

        Args:
            click_time: Time position in seconds

        Returns:
            Tuple of (start_time, end_time) for the segment
        """
        # If no slices or empty list, return full audio range
        if not self.current_slices:
            logger.debug("No segments defined, using full audio range")
            return 0, self.model.total_time

        # Special case for before the first segment marker
        # We use a special threshold for clicks near the start
        # This allows the start marker to be draggable while still allowing first segment playback
        first_slice = self.current_slices[0]
        if click_time <= first_slice:
            # For clicks very close to start, use first segment
            logger.debug("### FIRST SEGMENT DETECTED")
            logger.debug("Click time (%s) <= first slice (%s)", click_time, first_slice)
            logger.debug("### Returning first segment: 0 to %s", first_slice)
            return 0, first_slice

        # Special case for after the last segment marker
        last_slice = self.current_slices[-1]
        if click_time >= last_slice:
            logger.debug("### Click time (%s) >= last slice (%s)", click_time, last_slice)
            return last_slice, self.model.total_time

        # Middle segments
        for i, slice_time in enumerate(self.current_slices):
            if click_time < slice_time:
                if i == 0:  # Should not happen given the above check, but just in case
                    logger.debug("First segment (fallback): 0 to %s", slice_time)
                    return 0, slice_time
                else:
                    logger.debug("Middle segment %s: %s to %s", i, self.current_slices[i-1], slice_time)
                    return self.current_slices[i-1], slice_time

        # Fallback for safety - should not reach here
        logger.debug("Fallback: last segment - %s to %s", last_slice, self.model.total_time)
        return last_slice, self.model.total_time

    def handle_loop_playback(self) -> bool:
        """Handle looping of the current segment according to playback mode.

        Called when playback of a segment ends. Determines whether to restart
        playback based on the current playback mode (loop or loop-reverse).

        Returns:
            True if looping was initiated, False otherwise
        """
        start, end = self.current_segment

        if start is None or end is None:
            logger.debug("### No current segment to loop")
            return False

        match self.playback_mode:
            case PlaybackMode.LOOP:
                # Simple loop - play the same segment again
                logger.debug("### Loop playback: %ss to %ss", start, end)
                self.model.play_segment(start, end)
                return True

            case PlaybackMode.LOOP_REVERSE:
                # Loop with direction change
                if self.is_playing_reverse:
                    # Just finished reverse playback, now play forward
                    logger.debug("### Loop-reverse: Forward playback %ss to %ss", start, end)
                    self.is_playing_reverse = False
                    self.model.play_segment(start, end, reverse=False)
                else:
                    # Just finished forward playback, now play reverse
                    logger.debug("### Loop-reverse: Reverse playback %ss to %ss", end, start)
                    self.is_playing_reverse = True
                    # Use reverse=True to properly play the segment in reverse
                    self.model.play_segment(start, end, reverse=True)
                return True

            case _:
                # Not a looping mode
                return False

    def handle_plot_click(self, click_time: float) -> None:
        """Handle a click on the plot waveform.

        Determines segment boundaries for the clicked position and initiates
        playback of that segment.

        Args:
            click_time: Time position in seconds where the click occurred
        """
        logger.debug("### Handle plot click with time: %s", click_time)

        start_time, end_time = self.get_segment_boundaries(click_time)
        logger.debug("Segment boundaries: %s to %s", start_time, end_time)
        if start_time is not None and end_time is not None:
            # Use the click_time for determining the segment via play_segment
            self.play_segment(click_time)

    def update_slices(self, slices: list[float]) -> None:
        """Update the current slice markers.

        Called when segment boundaries change. Stores the slice positions
        for use in determining segment boundaries during playback.

        Args:
            slices: List of time positions (in seconds) where segments are divided
        """
        self.current_slices = slices
        logger.debug("Updated slices: %s", slices)

    def set_tempo_info(self, tempo: float, target_bpm: int, playback_tempo_enabled: bool) -> None:
        """Set tempo information for logging purposes.

        This is a temporary method to provide tempo context for logging.
        In the future, tempo management should be handled by a separate controller.

        Args:
            tempo: Current tempo in BPM
            target_bpm: Target tempo for playback adjustment
            playback_tempo_enabled: Whether playback tempo adjustment is enabled
        """
        self._tempo = tempo
        self._target_bpm = target_bpm
        self._playback_tempo_enabled = playback_tempo_enabled
