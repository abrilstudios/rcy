"""AudioController - Handles audio file loading and preset management.

This controller is responsible for:
- Loading audio files and initializing the audio processor
- Managing presets (loading, listing available presets)
- Updating UI elements related to audio file state
- Managing tempo calculations based on loaded audio
"""

from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal
from config_manager import config
import logging

logger = logging.getLogger(__name__)


class AudioController(QObject):
    """Handles audio file loading and preset management.

    This controller manages the lifecycle of audio file loading, including:
    - Setting the audio file in the model
    - Calculating and updating tempo based on measures
    - Synchronizing playback tempo settings
    - Updating view elements (waveform, tempo display, markers)
    - Loading and managing presets

    Signals:
        audio_file_loaded: Emitted when an audio file is successfully loaded
            Args: filename (str), total_time (float)
        preset_loaded: Emitted when a preset is successfully loaded
            Args: preset_id (str)
    """

    # Signals
    audio_file_loaded = pyqtSignal(str, float)  # filename, total_time
    preset_loaded = pyqtSignal(str)  # preset_id

    def __init__(self, model: Any, view: Any) -> None:
        """Initialize the AudioController.

        Args:
            model: The WavAudioProcessor model instance
            view: The RcyView view instance
        """
        super().__init__()
        self.model = model
        self.view = view

    def load_audio_file(
        self,
        filename: str,
        num_measures: int,
        playback_tempo_enabled: bool,
        target_bpm: int
    ) -> bool:
        """Load an audio file from filename.

        This method performs the complete audio file loading workflow:
        1. Sets the filename in the model
        2. Calculates tempo based on the number of measures
        3. Synchronizes source BPM and target BPM
        4. Disables playback tempo adjustment by default
        5. Updates all view elements (waveform, tempo, markers)

        Args:
            filename: Path to the audio file to load
            num_measures: Number of measures for tempo calculation
            playback_tempo_enabled: Whether playback tempo adjustment is enabled
            target_bpm: Target BPM for playback tempo adjustment

        Returns:
            bool: True if the file was loaded successfully, False otherwise
        """
        logger.debug("\n===== DETAILED AUDIO FILE LOADING AND TEMPO CALCULATION =====")
        logger.debug("Loading file: %s", filename)
        logger.debug("Initial state:")
        logger.debug("- Initial target BPM: %s", target_bpm)

        # Set the filename in the model
        logger.debug("Setting filename in model...")
        self.model.set_filename(filename)

        # Get audio information
        logger.debug("\nAudio file information:")
        logger.debug("- Sample rate: %s Hz", self.model.sample_rate)

        # Calculate tempo based on current measure count
        logger.debug("\nCalculating tempo from model.get_tempo(%s)...", num_measures)
        tempo = self.model.get_tempo(num_measures)
        logger.debug("Calculated tempo: %s BPM", tempo)

        # Calculate source BPM for playback tempo adjustment
        logger.debug("Calling model.calculate_source_bpm(measures=%s)...", num_measures)
        source_bpm = self.model.calculate_source_bpm(measures=num_measures)
        logger.debug("model.calculate_source_bpm returned: %s BPM", source_bpm)

        # Ensure model's source BPM matches the calculated tempo
        self.model.source_bpm = tempo
        logger.debug("Ensuring model.source_bpm equals tempo: %s BPM", self.model.source_bpm)

        # IMPORTANT FIX: Explicitly set target BPM to match the calculated tempo
        updated_target_bpm = int(round(tempo))

        # Ensure model's source_bpm stays consistent with the calculated tempo
        old_source_bpm = self.model.source_bpm
        if old_source_bpm != tempo:
            logger.debug("Synchronizing model.source_bpm from %s to %s BPM", old_source_bpm, tempo)
            self.model.source_bpm = tempo

        # Disable playback tempo adjustment by default for imported files
        updated_playback_tempo_enabled = False

        # Update the model's playback tempo settings
        logger.debug("Calling model.set_playback_tempo(%s, %s)", updated_playback_tempo_enabled, updated_target_bpm)
        ratio = self.model.set_playback_tempo(updated_playback_tempo_enabled, updated_target_bpm)

        # Update view first to get everything initialized
        logger.debug("\nUpdating view...")
        # Note: view update is handled by the main controller
        # self.view.update_scroll_bar is called by the main controller

        # Update the main tempo display
        logger.debug("Updating tempo display to %s BPM", tempo)
        self.view.update_tempo(tempo)

        # Update the measures display in the UI without triggering the callback
        logger.debug("Updating measures input to %s", num_measures)
        old_state = self.view.measures_input.blockSignals(True)
        self.view.measures_input.setText(str(num_measures))
        self.view.measures_input.blockSignals(old_state)

        # Update the playback tempo UI elements to match
        self.view.update_playback_tempo_display(
            updated_playback_tempo_enabled,
            updated_target_bpm,
            ratio
        )

        # Now reset markers after everything is updated
        logger.debug("Resetting markers to file boundaries")
        self.view.clear_markers()

        logger.debug("Final state after loading:")
        logger.debug("- Audio file: %s", filename)
        logger.debug("- Measures: %s", num_measures)
        logger.debug("- Source BPM: %s BPM", self.model.source_bpm)
        logger.debug("- Playback tempo enabled: %s", updated_playback_tempo_enabled)
        logger.debug("- Playback ratio: %.4f", ratio)
        logger.debug("===== END DETAILED AUDIO FILE LOADING AND TEMPO CALCULATION =====\n")

        # Emit signal with the loaded file information
        self.audio_file_loaded.emit(filename, self.model.total_time)

        return True

    def load_preset(self, preset_id: str, num_measures: int) -> bool:
        """Load a preset by its ID.

        This method:
        1. Retrieves preset information from config
        2. Loads the preset in the model
        3. Updates the number of measures if specified in the preset
        4. Recalculates tempo based on the new measure count
        5. Updates all view elements

        Args:
            preset_id: The ID of the preset to load
            num_measures: Current number of measures (may be overridden by preset)

        Returns:
            bool: True if the preset was loaded successfully, False otherwise
        """
        # Get preset info
        preset_info = config.get_preset_info(preset_id)
        if not preset_info:
            logger.debug("Preset '%s' not found", preset_id)
            return False

        # Load the preset in the model
        try:
            self.model.load_preset(preset_id)

            # Update number of measures if specified in the preset
            measures = preset_info.get('measures', 1)
            updated_num_measures = measures
            logger.debug("Preset '%s' specifies %s measures", preset_id, updated_num_measures)

            # Update the UI - only block signals if needed
            # Temporarily block signals to avoid recursive updates
            old_state = self.view.measures_input.blockSignals(True)
            self.view.measures_input.setText(str(updated_num_measures))
            self.view.measures_input.blockSignals(old_state)

            # Update tempo - This will now be calculated with the correct measure count
            tempo = self.model.get_tempo(updated_num_measures)
            logger.debug("Tempo: %s BPM based on %s measures", tempo, updated_num_measures)

            # Calculate source BPM for playback tempo adjustment
            self.model.calculate_source_bpm(measures=updated_num_measures)

            # Update view
            # Note: view update and scroll bar update are handled by main controller
            self.view.update_tempo(tempo)

            # Reset markers to file boundaries after view update
            self.view.clear_markers()

            # Update playback tempo display
            self.view.update_playback_tempo_display(
                False,  # playback_tempo_enabled - default to disabled for presets
                int(round(tempo)),  # target_bpm
                self.model.get_playback_ratio()
            )

            # Emit signal with the loaded preset information
            self.preset_loaded.emit(preset_id)

            return True
        except Exception as e:
            logger.debug("Failed to load preset '%s': %s", preset_id, e)
            return False

    def get_available_presets(self) -> list[tuple[str, str]]:
        """Get a list of available presets.

        Returns:
            list[tuple[str, str]]: List of (preset_id, preset_name) tuples
        """
        return config.get_preset_list()
