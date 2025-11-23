"""ApplicationController - Main orchestrator for the RCY application.

This controller integrates all domain-specific controllers and maintains
the exact same public API as the original RcyController for backward compatibility.

Architecture:
- Delegates operations to specialized controllers (audio, tempo, playback, etc.)
- Maintains shared state across controllers
- Coordinates inter-controller communication
- Handles signal wiring and event routing
"""

from typing import Any
from PyQt6.QtCore import QTimer
from audio_processor import WavAudioProcessor
from config_manager import config
from view_state import ViewState
from enums import PlaybackMode, SplitMethod
from commands import (
    ZoomInCommand, ZoomOutCommand, PanCommand,
    AddSegmentCommand, RemoveSegmentCommand, PlaySegmentCommand, CutAudioCommand,
    SetMeasuresCommand, SetThresholdCommand, SetResolutionCommand,
    SplitAudioCommand, LoadPresetCommand
)
import logging

# Import all domain controllers
from controllers.audio_controller import AudioController
from controllers.tempo_controller import TempoController
from controllers.playback_controller import PlaybackController
from controllers.segment_controller import SegmentController
from controllers.export_controller import ExportController
from controllers.view_controller import ViewController

logger = logging.getLogger(__name__)

# Map command names to command classes
COMMAND_MAP: dict[str, type] = {
    'zoom_in': ZoomInCommand,
    'zoom_out': ZoomOutCommand,
    'pan': PanCommand,
    'add_segment': AddSegmentCommand,
    'remove_segment': RemoveSegmentCommand,
    'play_segment': PlaySegmentCommand,
    'cut_audio': CutAudioCommand,
    'set_measures': SetMeasuresCommand,
    'set_threshold': SetThresholdCommand,
    'set_resolution': SetResolutionCommand,
    'split_audio': SplitAudioCommand,
    'load_preset': LoadPresetCommand,
}


class ApplicationController:
    """Main application controller that orchestrates all domain controllers.

    This controller maintains backward compatibility with the original RcyController
    while delegating functionality to specialized domain controllers:

    - AudioController: Audio file loading and preset management
    - TempoController: BPM calculations and measure management
    - PlaybackController: Playback control and looping
    - SegmentController: Segment manipulation and splitting
    - ExportController: Audio segment export operations
    - ViewController: View updates, zooming, and visualization

    Shared State:
        - tempo: Current tempo in BPM
        - num_measures: Number of measures in the audio
        - threshold: Transient detection threshold
        - measure_resolution: Beat resolution for splitting
        - playback_tempo_enabled: Whether playback tempo adjustment is enabled
        - target_bpm: Target BPM for playback tempo adjustment
        - playback_mode: Playback mode (one-shot, loop)
        - start_marker_pos: Start marker position in seconds
        - end_marker_pos: End marker position in seconds
        - visible_time: Visible time window in seconds
    """

    def __init__(self, model: WavAudioProcessor) -> None:
        """Initialize the ApplicationController.

        Args:
            model: The WavAudioProcessor model instance
        """
        self.model = model
        self.view = None

        # Initialize view state
        self.visible_time = 10  # Initial visible time window
        self.view_state = ViewState(self.model.total_time, self.visible_time)

        # Shared state - configuration from config
        self.num_measures = 1
        self.measure_resolution = 4
        self.tempo = 120

        # Get transient detection parameters from config
        td_config = config.get_setting("audio", "transientDetection", {})
        self.threshold = td_config.get("threshold", 0.20)

        # Get playback tempo parameters from config
        pt_config = config.get_setting("audio", "playbackTempo", {})
        self.playback_tempo_enabled = pt_config.get("enabled", False)
        self.target_bpm = pt_config.get("targetBpm", 120)

        # Get playback mode from config
        playback_config = config.get_setting("audio", "playback", {})
        mode_str = playback_config.get("mode", PlaybackMode.ONE_SHOT)

        # Validate playback mode
        try:
            self.playback_mode = PlaybackMode(mode_str)
        except ValueError:
            logger.warning("Warning: Invalid playback mode '%s', using 'one-shot'", mode_str)
            self.playback_mode = PlaybackMode.ONE_SHOT

        # Marker positions
        self.start_marker_pos = None
        self.end_marker_pos = None

        # Initialize all sub-controllers (view will be set later)
        self.audio_ctrl = AudioController(model, None)
        self.tempo_ctrl = TempoController(model, None)
        self.playback_ctrl = PlaybackController(model, None)
        self.segment_ctrl = SegmentController(model, None)
        self.export_ctrl = ExportController(model, None)

        # ViewController needs view_state
        self.view_ctrl = ViewController(model, None, self.view_state)

        # Synchronize initial state with controllers
        self._sync_state_to_controllers()

        # Setup timer to check playback status periodically
        self.playback_check_timer = QTimer()
        self.playback_check_timer.timeout.connect(self.check_playback_status)
        self.playback_check_timer.start(100)  # Check every 100ms

        logger.debug("ApplicationController initialized with playback_mode: %s", self.playback_mode)

    def _sync_state_to_controllers(self) -> None:
        """Synchronize shared state to all controllers."""
        # Sync tempo state
        self.tempo_ctrl.tempo = self.tempo
        self.tempo_ctrl.num_measures = self.num_measures
        self.tempo_ctrl.measure_resolution = self.measure_resolution
        self.tempo_ctrl.playback_tempo_enabled = self.playback_tempo_enabled
        self.tempo_ctrl.target_bpm = self.target_bpm
        self.tempo_ctrl.start_marker_pos = self.start_marker_pos
        self.tempo_ctrl.end_marker_pos = self.end_marker_pos

        # Sync playback state
        self.playback_ctrl.playback_mode = self.playback_mode

        # Sync segment state
        self.segment_ctrl.measure_resolution = self.measure_resolution

        # Sync export state
        self.export_ctrl.tempo = self.tempo
        self.export_ctrl.num_measures = self.num_measures
        self.export_ctrl.start_marker_pos = self.start_marker_pos
        self.export_ctrl.end_marker_pos = self.end_marker_pos

        # Sync view state
        self.view_ctrl.visible_time = self.visible_time

    def set_view(self, view: Any) -> None:
        """Set the view and wire up all connections.

        Args:
            view: The RcyView view instance
        """
        self.view = view

        # Update all controllers with view
        self.audio_ctrl.view = view
        self.tempo_ctrl.view = view
        self.playback_ctrl.view = view
        self.segment_ctrl.view = view
        self.export_ctrl.view = view
        self.view_ctrl.view = view

        # Wire up view signals to controller methods
        self.view.measures_changed.connect(self.on_measures_changed)
        self.view.threshold_changed.connect(self.on_threshold_changed)

        # Route segment manipulation through command dispatcher
        self.view.remove_segment.connect(
            lambda pos: self.execute_command('remove_segment', position=pos)
        )
        self.view.add_segment.connect(
            lambda pos: self.execute_command('add_segment', position=pos)
        )
        self.view.play_segment.connect(
            lambda pos: self.execute_command('play_segment', position=pos)
        )

        # Connect marker signals
        self.view.start_marker_changed.connect(self.on_start_marker_changed)
        self.view.end_marker_changed.connect(self.on_end_marker_changed)

        # Route cut action through command dispatcher
        self.view.cut_requested.connect(
            lambda start, end: self.execute_command('cut_audio', start=start, end=end)
        )

        # Initialize playback tempo UI
        self.view.update_playback_tempo_display(
            self.playback_tempo_enabled,
            self.target_bpm,
            1.0  # Initial ratio
        )

        # Set initial playback mode in view
        self.view.update_playback_mode_menu(self.playback_mode)

    def execute_command(self, name: str, **kwargs: Any) -> Any:
        """Instantiate and execute a Command by name, passing kwargs to its constructor.

        Args:
            name: Command name to execute
            **kwargs: Arguments to pass to the command constructor

        Returns:
            Result of command execution

        Raises:
            KeyError: If command name is unknown
        """
        cmd_cls = COMMAND_MAP.get(name)
        if not cmd_cls:
            raise KeyError(f"Unknown command: {name}")
        cmd = cmd_cls(self, **kwargs)
        return cmd.execute()

    # ========== Audio Loading and Presets ==========

    def load_audio_file(self, filename: str) -> bool:
        """Load an audio file from filename.

        Args:
            filename: Path to the audio file to load

        Returns:
            bool: True if the file was loaded successfully
        """
        result = self.audio_ctrl.load_audio_file(
            filename, self.num_measures,
            self.playback_tempo_enabled, self.target_bpm
        )

        if result:
            # Update shared state from model
            self.tempo = self.model.get_tempo(self.num_measures)
            self.target_bpm = int(round(self.tempo))
            self.playback_tempo_enabled = False

            # Sync to controllers
            self._sync_state_to_controllers()

            # Update view
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)

        return result

    def load_preset(self, preset_id: str) -> bool:
        """Load a preset by its ID.

        Args:
            preset_id: The ID of the preset to load

        Returns:
            bool: True if the preset was loaded successfully
        """
        # Get preset info to check for measure count
        preset_info = config.get_preset_info(preset_id)
        if preset_info:
            measures = preset_info.get('measures', 1)
            self.num_measures = measures

        result = self.audio_ctrl.load_preset(preset_id, self.num_measures)

        if result:
            # Update shared state
            self.tempo = self.model.get_tempo(self.num_measures)

            # Sync to controllers
            self._sync_state_to_controllers()

            # Update view
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)

        return result

    def get_available_presets(self) -> list[dict[str, Any]]:
        """Get a list of available presets.

        Returns:
            List of preset information dictionaries
        """
        return self.audio_ctrl.get_available_presets()

    # ========== Tempo Management ==========

    def get_tempo(self) -> float:
        """Get the current tempo in BPM.

        Returns:
            Current tempo value
        """
        return self.tempo

    def on_measures_changed(self, num_measures: int) -> None:
        """Handle measure count change and recalculate tempo.

        Args:
            num_measures: The new number of measures
        """
        # Update shared state
        self.num_measures = num_measures

        # Update controller state
        self.tempo_ctrl.num_measures = num_measures
        self.tempo_ctrl.playback_tempo_enabled = self.playback_tempo_enabled
        self.tempo_ctrl.target_bpm = self.target_bpm

        # Delegate to tempo controller
        self.tempo_ctrl.on_measures_changed(num_measures)

        # Sync back shared state from controller
        self.tempo = self.tempo_ctrl.tempo
        self.target_bpm = self.tempo_ctrl.target_bpm

        # Update export controller state
        self.export_ctrl.tempo = self.tempo
        self.export_ctrl.num_measures = self.num_measures

    def on_start_marker_changed(self, position: float) -> None:
        """Handle start marker position change.

        Args:
            position: New start marker position in seconds
        """
        self.start_marker_pos = position
        self.tempo_ctrl.start_marker_pos = position
        self.export_ctrl.start_marker_pos = position
        self.tempo_ctrl.on_start_marker_changed(position)

        # Sync back tempo if changed
        self.tempo = self.tempo_ctrl.tempo
        self.target_bpm = self.tempo_ctrl.target_bpm

    def on_end_marker_changed(self, position: float) -> None:
        """Handle end marker position change.

        Args:
            position: New end marker position in seconds
        """
        self.end_marker_pos = position
        self.tempo_ctrl.end_marker_pos = position
        self.export_ctrl.end_marker_pos = position
        self.tempo_ctrl.on_end_marker_changed(position)

        # Sync back tempo if changed
        self.tempo = self.tempo_ctrl.tempo
        self.target_bpm = self.tempo_ctrl.target_bpm

    def set_measure_resolution(self, resolution: int) -> None:
        """Set the measure resolution without automatically triggering a split.

        Args:
            resolution: The new measure resolution value
        """
        self.measure_resolution = resolution
        self.tempo_ctrl.set_measure_resolution(resolution)
        self.segment_ctrl.set_measure_resolution(resolution)

    # ========== Playback Control ==========

    def set_playback_mode(self, mode: str) -> bool:
        """Set the playback mode.

        Args:
            mode: One of 'one-shot' or 'loop'

        Returns:
            bool: True if mode was valid and set successfully
        """
        result = self.playback_ctrl.set_playback_mode(mode)
        if result:
            self.playback_mode = mode
        return result

    def get_playback_mode(self) -> str:
        """Get the current playback mode.

        Returns:
            Current playback mode string
        """
        return self.playback_mode

    def play_segment(self, click_time: float) -> None:
        """Play or stop a segment based on click location.

        Args:
            click_time: Time position in seconds where the click occurred
        """
        self.playback_ctrl.play_segment(click_time)

    def stop_playback(self) -> None:
        """Stop any currently playing audio."""
        self.playback_ctrl.stop_playback()

    def play_selected_region(self) -> None:
        """Play or stop the audio between start and end markers."""
        self.playback_ctrl.play_selected_region()

    def get_segment_boundaries(self, click_time: float) -> tuple[float, float]:
        """Get the start and end times for the segment containing the click.

        Args:
            click_time: Time position in seconds

        Returns:
            Tuple of (start_time, end_time) for the segment
        """
        return self.playback_ctrl.get_segment_boundaries(click_time)

    def handle_plot_click(self, click_time: float) -> None:
        """Handle a click on the plot waveform.

        Args:
            click_time: Time position in seconds where the click occurred
        """
        self.playback_ctrl.handle_plot_click(click_time)

    def handle_loop_playback(self) -> bool:
        """Handle looping of the current segment according to playback mode.

        Returns:
            True if looping was initiated, False otherwise
        """
        return self.playback_ctrl.handle_loop_playback()

    def check_playback_status(self) -> None:
        """Periodically check if playback has ended and handle looping."""
        if self.model.playback_just_ended:
            logger.debug("### Controller detected playback just ended")

            # Reset the flag
            self.model.playback_just_ended = False

            # Handle looping if needed
            # Get current mode from playback controller to ensure consistency
            current_mode = self.playback_ctrl.playback_mode
            logger.debug("### Current playback mode: %s", current_mode)
            if current_mode == PlaybackMode.LOOP:
                logger.debug("### Mode is looping, calling handle_loop_playback()")
                if self.handle_loop_playback():
                    logger.debug("### Loop playback initiated")
                    return
                else:
                    logger.debug("### Loop playback returned False")

            # If not looping or loop handling failed, clear highlight
            self.view.clear_active_segment_highlight()

    def set_playback_tempo(self, enabled: bool, target_bpm: int | None = None) -> float:
        """Configure playback tempo settings.

        Args:
            enabled: Whether tempo adjustment is enabled
            target_bpm: Target tempo in BPM (optional)

        Returns:
            The adjustment factor (ratio of target to source tempo)
        """
        # Update controller state
        self.playback_tempo_enabled = enabled

        if target_bpm is not None:
            self.target_bpm = int(target_bpm)

        # Update model with settings
        playback_ratio = self.model.set_playback_tempo(
            enabled,
            self.target_bpm
        )

        # Update view with new playback tempo settings
        self.view.update_playback_tempo_display(
            enabled,
            self.target_bpm,
            playback_ratio
        )

        # Sync to tempo controller
        self.tempo_ctrl.playback_tempo_enabled = enabled
        self.tempo_ctrl.target_bpm = self.target_bpm

        return playback_ratio

    # ========== Segment Management ==========

    def add_segment(self, click_time: float) -> None:
        """Add a new segment at the specified time position.

        Args:
            click_time: Time position where the segment should be added
        """
        self.segment_ctrl.add_segment(click_time)

    def remove_segment(self, click_time: float) -> None:
        """Remove the segment at the specified time position.

        Args:
            click_time: Time position of the segment to remove
        """
        self.segment_ctrl.remove_segment(click_time)

    def split_audio(self, method: str | SplitMethod = SplitMethod.MEASURES, measure_resolution: int | None = None) -> None:
        """Split audio into segments using the specified method.

        Args:
            method: Split method - either 'measures' or 'transients'
            measure_resolution: Resolution for measure-based splits (optional)

        Raises:
            ValueError: If an invalid split method is specified
        """
        # Convert string to enum if necessary
        if isinstance(method, str):
            method = SplitMethod(method)

        match method:
            case SplitMethod.MEASURES:
                resolution = measure_resolution if measure_resolution is not None else self.measure_resolution
                self.segment_ctrl.split_audio(
                    method=SplitMethod.MEASURES,
                    measure_resolution=resolution,
                    num_measures=self.num_measures
                )
            case SplitMethod.TRANSIENTS:
                self.segment_ctrl.split_audio(
                    method=SplitMethod.TRANSIENTS,
                    threshold=self.threshold
                )
            case _:
                raise ValueError(f"Invalid split method: {method}")

        # Update playback controller's slices
        slices = self.model.segment_manager.get_boundaries()
        self.playback_ctrl.update_slices(slices)

    def on_threshold_changed(self, threshold: float) -> None:
        """Handle transient detection threshold change.

        Args:
            threshold: New threshold value
        """
        self.threshold = threshold
        self.split_audio(method=SplitMethod.TRANSIENTS)

    # ========== Export ==========

    def export_segments(self, directory: str) -> list[str]:
        """Export audio segments to files.

        Args:
            directory: Target directory path for exported files

        Returns:
            List of exported file paths
        """
        # Ensure export controller has current state
        self.export_ctrl.tempo = self.tempo
        self.export_ctrl.num_measures = self.num_measures
        self.export_ctrl.start_marker_pos = self.start_marker_pos
        self.export_ctrl.end_marker_pos = self.end_marker_pos

        return self.export_ctrl.export_segments(directory)

    # ========== View Management ==========

    def update_view(self) -> None:
        """Update the view with current audio data and segment information."""
        self.view_ctrl.update_view()

        # Also update playback controller's slices
        slices = self.model.segment_manager.get_boundaries()
        self.playback_ctrl.update_slices(slices)

    def zoom_in(self) -> None:
        """Zoom in on the waveform by shrinking the visible time window."""
        self.view_ctrl.zoom_in()
        self.visible_time = self.view_ctrl.visible_time

    def zoom_out(self) -> None:
        """Zoom out from the waveform by expanding the visible time window."""
        self.view_ctrl.zoom_out()
        self.visible_time = self.view_ctrl.visible_time

    # ========== Audio Editing ==========

    def cut_audio(self, start_time: float, end_time: float) -> None:
        """Trim the audio to the selected region.

        Args:
            start_time: Start time of the region to keep
            end_time: End time of the region to keep
        """
        # Convert time positions to sample positions
        start_sample = self.model.get_sample_at_time(start_time)
        end_sample = self.model.get_sample_at_time(end_time)

        # Perform the cut operation in the model
        success = self.model.cut_audio(start_sample, end_sample)
        if not success:
            logger.debug("Failed to trim audio")
            return

        # Update tempo and clear segments
        self.tempo = self.model.get_tempo(self.num_measures)
        self.view.update_tempo(self.tempo)
        self.model.segments = []

        # Sync state to controllers
        self._sync_state_to_controllers()

        # Update the view with the new trimmed audio
        self.update_view()
        self.view.update_scroll_bar(self.visible_time, self.model.total_time)

        # Ensure markers are within bounds after cut
        self.view.waveform_view._clamp_markers_to_data_bounds()

        logger.debug("Audio successfully trimmed")

    # ========== Backward Compatibility Properties ==========

    @property
    def current_slices(self) -> list[float]:
        """Get current segment slices (for backward compatibility).

        Returns:
            List of segment boundary time positions
        """
        return self.playback_ctrl.current_slices

    @current_slices.setter
    def current_slices(self, slices: list[float]) -> None:
        """Set current segment slices (for backward compatibility).

        Args:
            slices: List of segment boundary time positions
        """
        self.playback_ctrl.current_slices = slices

    def crop_to_markers(self, start_time: float, end_time: float) -> bool:
        """Crop audio to the region between start and end markers.

        This trims the audio file to only include the region between the markers.
        All segments and slices are reset after cropping.

        Args:
            start_time: Start marker position in seconds
            end_time: End marker position in seconds

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Cropping audio from %ss to %ss", start_time, end_time)

        # Perform the crop in the model
        success = self.model.crop_to_time_range(start_time, end_time)

        if success:
            # Update tempo calculation based on new file length
            self.tempo = self.model.get_tempo(self.num_measures)

            # Sync state to all controllers
            self._sync_state_to_controllers()

            # Update the view
            self.update_view()
            self.view.update_scroll_bar(self.visible_time, self.model.total_time)

            # Reset markers to new file boundaries
            self.view.clear_markers()

            logger.info("Successfully cropped audio, new duration: %ss", self.model.total_time)

        return success
