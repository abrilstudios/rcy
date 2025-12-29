import numpy as np
import soundfile as sf
import librosa
import os
import pathlib
import sys
import threading
from typing import Any

from config_manager import config
from error_handler import ErrorHandler
from segment_manager import get_segment_manager, SegmentObserver, SegmentManager
from custom_types import AudioArray, TimeArray, PresetInfo, PlaybackEndedCallback

import logging

logger = logging.getLogger(__name__)
# Import the ring buffer audio engine
from ring_buffer_audio import RingBufferAudioEngine
from enums import PlaybackMode

# Import audio processing functions from shared utils
from audio_utils import (
    extract_segment, resample_to_standard_rate,
    apply_tail_fade, reverse_segment, process_segment_for_output
)


class AudioEngineObserver(SegmentObserver):
    """Observer that keeps audio engine synchronized with segment changes."""

    audio_engine: RingBufferAudioEngine

    def __init__(self, audio_engine: RingBufferAudioEngine) -> None:
        self.audio_engine = audio_engine

    def on_segments_changed(self, operation: str, **kwargs: Any) -> None:
        """Update audio engine when segments change."""
        # Audio engine doesn't need segment updates - it plays based on time ranges
        # Segments are managed by SegmentManager and used by controllers
        pass


class WavAudioProcessor:
    # Instance attributes
    preset_id: str
    preset_info: PresetInfo | None
    is_playing: bool
    playback_just_ended: bool
    is_stereo: bool
    channels: int
    segment_manager: SegmentManager
    audio_engine: RingBufferAudioEngine
    audio_observer: AudioEngineObserver
    playback_tempo_enabled: bool
    target_bpm: int
    source_bpm: float
    filename: str
    sample_rate: int
    total_time: float
    data_left: AudioArray
    data_right: AudioArray
    time: TimeArray

    def __init__(
        self,
        duration: float = 2.0,
        sample_rate: int = 44100,
        preset_id: str = 'amen_classic'
    ) -> None:
        self.preset_id = preset_id
        self.preset_info = None
        self.is_playing = False
        self.playback_just_ended = False  # Flag to indicate playback has just ended
        self.playback_ended_event = threading.Event()  # Event for waiting on playback completion
        self.is_stereo = False
        self.channels = 1

        # Initialize centralized segment management
        self.segment_manager = get_segment_manager()

        # Initialize ring buffer audio engine
        logger.debug("Using ring buffer audio engine")
        self.audio_engine = RingBufferAudioEngine(
            sample_rate=sample_rate,
            channels=2,  # Always use stereo for compatibility
            blocksize=256  # Low latency block size
        )
        self.audio_engine.set_playback_ended_callback(self._on_playback_ended)

        # Set up observer to keep audio engine synchronized with segment changes
        self.audio_observer = AudioEngineObserver(self.audio_engine)
        self.segment_manager.add_observer(self.audio_observer)

        # Initialize playback tempo settings
        self._init_playback_tempo()

        # Try to load the specified preset
        try:
            self.load_preset(preset_id)
        except Exception as e:
            logger.debug("Failed to load preset: %s", e)
            sys.exit(1)
    
    def _init_playback_tempo(self) -> None:
        """Initialize playback tempo settings from config"""
        # Get playback tempo config with defaults
        pt_config = config.get_setting("audio", "playbackTempo", {})

        # Read settings with defaults
        self.playback_tempo_enabled = pt_config.get("enabled", False)
        self.target_bpm = int(pt_config.get("targetBpm", 120))

        # Source BPM is calculated from audio duration and measures
        # Will be set properly after loading preset
        self.source_bpm = 120.0  # Default value

        logger.debug("Playback tempo initialized: enabled=%s", self.playback_tempo_enabled)

    def _on_playback_ended(self) -> None:
        """Callback from audio engine when playback ends"""
        self.playback_just_ended = True
        self.is_playing = False
        self.playback_ended_event.set()  # Signal waiters that playback ended

    def load_preset(self, preset_id: str) -> PresetInfo | None:
        """Load an audio preset by its ID"""
        # Get preset info from config
        self.preset_info = config.get_preset_info(preset_id)
        if not self.preset_info:
            raise ValueError(f"Preset '{preset_id}' not found")

        # Get the project root to resolve relative paths
        current_file = pathlib.Path(__file__)
        project_root = current_file.parent.parent.parent

        # Resolve the filepath
        filepath = self.preset_info.get('filepath')
        if not filepath:
            raise ValueError(f"No filepath defined for preset '{preset_id}'")

        # Handle relative paths
        if not os.path.isabs(filepath):
            filepath = os.path.join(project_root, filepath)

        # Check if file exists
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Audio file not found: {filepath}")

        # Load the audio file
        self.set_filename(filepath)

        # Return the preset info for convenience
        return self.preset_info
        
    def set_filename(self, filename: str):
        """Load an audio file and initialize all audio processing components.

        This is the main entry point for loading audio. It orchestrates:
        1. Loading file metadata
        2. Initializing audio buffers
        3. Setting up segment management
        4. Calculating source BPM from preset info
        """
        try:
            self._load_file_metadata(filename)
            self._initialize_audio_buffers()
            self._set_measures_and_calculate_bpm()
        except Exception as e:
            logger.warning("Error loading audio file %s: %s", filename, e)
            raise

    def _load_file_metadata(self, filename: str):
        """Load audio file and extract metadata (sample rate, channels, duration)."""
        self.filename = filename
        with sf.SoundFile(filename) as sound_file:
            self.sample_rate = sound_file.samplerate
            # Enforce 44100 Hz sample rate for consistency
            if self.sample_rate != 44100:
                raise ValueError(
                    f"Unsupported sample rate: {self.sample_rate} Hz. "
                    f"RCY requires 44100 Hz audio files. "
                    f"Run 'python sample-packs/rhythm-lab/normalize_sample_rates.py' to convert."
                )
            self.channels = sound_file.channels
            self.is_stereo = self.channels > 1
            self.total_time = len(sound_file) / self.sample_rate

    def _initialize_audio_buffers(self):
        """Initialize audio data buffers and configure audio engine."""
        # Load audio data into left/right channels
        self.data_left, self.data_right = self._generate_data()

        # Create time array based on the actual data length
        self.time = np.linspace(0, self.total_time, len(self.data_left))

        # Initialize SegmentManager with audio context (creates single segment covering entire file)
        total_samples = len(self.data_left)
        self.segment_manager.set_audio_context(total_samples, self.sample_rate)

        # Initialize audio engine with source data
        self.audio_engine.set_source_audio(
            self.data_left, self.data_right, self.sample_rate, self.is_stereo
        )
        self.audio_engine.start_stream()

    def _set_measures_and_calculate_bpm(self) -> None:
        """Extract measures from preset info and calculate source BPM."""
        # Use the 'measures' field from preset_info if available
        measures: int | None = None
        try:
            measures = self.preset_info.get('measures', None) if self.preset_info else None
        except Exception:
            measures = None
        # Fallback to 1 measure if not specified
        if measures is None:
            measures = 1
        self.calculate_source_bpm(measures=measures)

    def _generate_data(self) -> tuple[AudioArray, AudioArray]:
        """Load audio data and return left and right channels (or mono duplicated if single channel)"""
        audio_data, _ = sf.read(self.filename, always_2d=True)

        if audio_data.shape[1] > 1:
            # Stereo file - separate channels
            data_left = audio_data[:, 0]
            data_right = audio_data[:, 1]

            # Ensure both channels have the same length (fix for shape mismatch errors)
            if len(data_left) != len(data_right):
                min_length = min(len(data_left), len(data_right))
                data_left = data_left[:min_length]
                data_right = data_right[:min_length]
                logger.debug("Trimmed stereo channels to same length %s for file %s", min_length, self.filename)
        else:
            # Mono file - duplicate the channel for consistency in code
            data_left = audio_data.flatten()
            data_right = data_left.copy()

        return data_left, data_right

    def get_data(
        self,
        start_time: float,
        end_time: float
    ) -> tuple[TimeArray, AudioArray, AudioArray]:
        """Get raw time and audio data for the specified time range.

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns tuple: (time, left_channel, right_channel)
        """
        start_idx = int(start_time * self.sample_rate)
        end_idx = int(end_time * self.sample_rate)

        # Get the raw data for the specified range
        time_slice = self.time[start_idx:end_idx]
        left_slice = self.data_left[start_idx:end_idx]
        right_slice = self.data_right[start_idx:end_idx]

        # Return raw data without any downsampling (model should be pure)
        return time_slice, left_slice, right_slice

    def get_tempo(
        self,
        num_measures: int,
        beats_per_measure: int = 4,
        start_time: float | None = None,
        end_time: float | None = None
    ) -> float:
        """Calculate tempo from region duration and measure count.

        Args:
            num_measures: Number of musical measures in the region
            beats_per_measure: Beats per measure (default 4 for 4/4 time)
            start_time: Start of region in seconds (defaults to 0)
            end_time: End of region in seconds (defaults to total_time)

        Returns:
            Calculated tempo in BPM
        """
        # Use provided region or default to full file
        start = start_time if start_time is not None else 0.0
        end = end_time if end_time is not None else self.total_time
        duration = end - start

        logger.debug("\n----- DETAILED GET_TEMPO CALCULATION -----")
        logger.debug("Input num_measures: %s", num_measures)
        logger.debug("Region: %ss to %ss (duration: %ss = %s minutes)",
                    start, end, duration, duration/60)

        total_beats = num_measures * beats_per_measure

        duration_minutes = duration / 60
        tempo = total_beats / duration_minutes

        logger.debug("Tempo calculation: %s beats / %s minutes = %s BPM",
                    total_beats, duration_minutes, tempo)

        return tempo

    def split_by_measures(self, num_measures: int, measure_resolution: int,
                         start_time: float | None = None, end_time: float | None = None) -> list[int]:
        """Split audio into equal divisions based on musical measures

        Args:
            num_measures: Number of musical measures in the audio
            measure_resolution: Number of divisions per measure
            start_time: Optional start time in seconds (defaults to 0)
            end_time: Optional end time in seconds (defaults to total_time)

        Returns:
            List of sample positions for the segments
        """
        # Use provided times or default to full file
        start = start_time if start_time is not None else 0.0
        end = end_time if end_time is not None else self.total_time

        # Use segment manager's centralized split method with consistent position calculation
        self.segment_manager.split_by_measures(num_measures, measure_resolution, start, end)

        # Return all boundaries for backward compatibility
        return self.segment_manager.get_boundaries()

    def split_by_transients(
        self,
        threshold: float | None = None,
        start_time: float | None = None,
        end_time: float | None = None
    ) -> list[int]:
        """Split audio by transient detection within a region.

        Args:
            threshold: Detection threshold (0-1), defaults to config value
            start_time: Start of region in seconds (defaults to 0)
            end_time: End of region in seconds (defaults to total_time)

        Returns:
            List of boundary positions in samples
        """
        # Get transient detection parameters from config
        td_config = config.get_setting("audio", "transientDetection", {})

        # Use provided threshold or fallback to config value or default
        if threshold is None:
            threshold = td_config.get("threshold", 0.2)

        # Get other parameters from config with defaults
        wait_time = td_config.get("waitTime", 1)
        pre_max = td_config.get("preMax", 1)
        post_max = td_config.get("postMax", 1)
        delta_factor = td_config.get("deltaFactor", 0.1)

        # Calculate delta based on the threshold and delta factor
        delta = threshold * delta_factor

        # Use provided region or default to full file
        start = start_time if start_time is not None else 0.0
        end = end_time if end_time is not None else self.total_time

        logger.debug("split_by_transients: threshold=%s, wait=%s, delta=%s, region=[%s, %s]",
                    threshold, wait_time, delta, start, end)

        # Use left channel for transient detection
        onset_env = librosa.onset.onset_strength(y=self.data_left, sr=self.sample_rate)
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=self.sample_rate,
            delta=delta,
            wait=wait_time,
            pre_max=pre_max,
            post_max=post_max,
        )
        onset_times = librosa.frames_to_time(onsets, sr=self.sample_rate)

        # Filter onsets to region (keep only those strictly inside L-R)
        filtered_times = [t for t in onset_times if start < t < end]

        # Build positions list: region start + filtered onsets + region end
        start_sample = int(start * self.sample_rate)
        end_sample = int(end * self.sample_rate)

        region_positions = [start_sample]
        region_positions.extend([int(t * self.sample_rate) for t in filtered_times])
        region_positions.append(end_sample)

        # Update SegmentManager with region boundaries (uses L/R, not 0/total)
        self.segment_manager.split_by_region_positions(region_positions)

        # Return all boundaries for backward compatibility
        return self.segment_manager.get_boundaries()

    def remove_segment(self, click_time: float) -> None:
        """Remove the segment closest to click_time."""
        try:
            self.segment_manager.remove_segment_boundary(click_time)
        except Exception as e:
            ErrorHandler.log_exception(e, context="WavAudioProcessor.remove_segment")
            return

    def add_segment(self, click_time: float) -> None:
        """Add a new segment at click_time."""
        try:
            self.segment_manager.add_segment_boundary(click_time)
        except Exception as e:
            ErrorHandler.log_exception(e, context="WavAudioProcessor.add_segment")
            return

    def get_segment_boundaries(self, click_time: float) -> tuple[float, float]:
        click_sample = int(click_time * self.sample_rate)
        segments = self.segment_manager.get_boundaries()
        data_length = len(self.data_left)  # Use left channel for length reference

        for i, segment in enumerate(segments):
            if click_sample < segment:
                if i == 0:
                    return 0, segment / self.sample_rate
                else:
                    return segments[i-1] / self.sample_rate, segment / self.sample_rate
        if segments:
            return segments[-1] / self.sample_rate, data_length / self.sample_rate
        else:
            return 0, data_length / self.sample_rate

    def play_segment(self, start_time: float, end_time: float, reverse: bool = False) -> bool:
        """Play a segment of audio using the high-performance engine

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            reverse: Whether to play the segment in reverse

        Returns:
            bool: True if playback started, False otherwise
        """
        logger.debug("### Model play_segment called with start_time=%s, end_time=%s, reverse=%s", start_time, end_time, reverse)

        # Clear the completion event before starting playback
        self.playback_ended_event.clear()

        # Play the segment
        self.is_playing = True
        return self.audio_engine.play_segment(start_time, end_time, reverse)

    def stop_playback(self) -> None:
        """Stop any currently playing audio"""
        self.audio_engine.stop_playback()
        self.is_playing = False

    def get_sample_at_time(self, time: float) -> int:
        return int(time * self.sample_rate)
    
    def calculate_source_bpm(
        self,
        measures: int | None = None,
        start_time: float | None = None,
        end_time: float | None = None
    ) -> float:
        """Calculate source BPM based on region duration and measure count.

        Formula: Source BPM = (60 × beats) / duration
        Where beats = measures × 4 (assuming 4/4 time signature)

        Args:
            measures: Number of musical measures in the region
            start_time: Start of region in seconds (defaults to 0)
            end_time: End of region in seconds (defaults to total_time)

        Returns:
            float: The calculated BPM value (self.source_bpm)
        """
        # Use provided region or default to full file
        start = start_time if start_time is not None else 0.0
        end = end_time if end_time is not None else self.total_time
        duration = end - start

        logger.debug("\n===== DETAILED BPM CALCULATION DEBUGGING =====")
        logger.debug("Input measures value: %s", measures)
        logger.debug("Region: %ss to %ss (duration: %ss)", start, end, duration)

        if duration <= 0:
            logger.warning("WARNING: Cannot calculate source BPM, invalid duration: %s", duration)
            self.source_bpm = 120.0  # Default fallback
            return self.source_bpm

        # Get beats per measure from config (default to 4/4 time signature)
        beats_per_measure = 4  # Standard 4/4 time for breakbeats
        logger.debug("Using beats_per_measure: %s", beats_per_measure)

        # Calculate total beats in the region
        if measures is None:
            measures = 1
        total_beats = measures * beats_per_measure

        # Calculate BPM based on total beats
        old_source_bpm = getattr(self, 'source_bpm', None)
        self.source_bpm = (60.0 * total_beats) / duration

        logger.debug("BPM CALCULATION: (%s × %s) / %s = %s BPM", 60.0, total_beats, duration, self.source_bpm)
        if old_source_bpm is not None:
            logger.debug("Source BPM changed from %s to %s", old_source_bpm, self.source_bpm)

        logger.debug("Final source BPM: %s BPM", self.source_bpm)
        logger.debug("===== END DETAILED BPM CALCULATION =====\n")

        return self.source_bpm

    def get_playback_ratio(self) -> float:
        """Calculate the playback ratio for tempo adjustment

        Formula: playbackRatio = targetBPM / sourceBPM
        """
        if not self.playback_tempo_enabled:
            return 1.0  # No adjustment

        if self.source_bpm <= 0:
            # Recalculate if needed
            self.calculate_source_bpm()

        if self.source_bpm <= 0:
            return 1.0  # Safety check

        # Calculate the ratio
        ratio = self.target_bpm / self.source_bpm

        logger.debug("Playback ratio: %s / %s = %s", self.target_bpm, self.source_bpm, ratio)
        return ratio

    def get_adjusted_sample_rate(self) -> int:
        """Get the sample rate adjusted for tempo change"""
        if not self.playback_tempo_enabled:
            return self.sample_rate

        # Calculate the playback ratio
        ratio = self.get_playback_ratio()

        # Apply ratio to sample rate
        adjusted_rate = int(self.sample_rate * ratio)

        logger.debug("Adjusted sample rate: %s Hz (original: %s Hz, ratio: %s)", adjusted_rate, self.sample_rate, ratio)
        return adjusted_rate

    def set_playback_tempo(self, enabled: bool, target_bpm: int | None = None) -> float:
        """Configure playback tempo settings

        Args:
            enabled: Whether tempo adjustment is enabled
            target_bpm: Target tempo in BPM

        Returns:
            The new playback ratio
        """
        self.playback_tempo_enabled = enabled

        if target_bpm is not None:
            self.target_bpm = int(target_bpm)

        # Ensure source BPM is calculated
        if self.source_bpm <= 0:
            self.calculate_source_bpm()

        logger.debug("Set playback tempo: enabled=%s, source_bpm=%s, target_bpm=%s", enabled, self.source_bpm, self.target_bpm)

        # Update audio engine immediately with new tempo settings
        self.audio_engine.set_playback_tempo(
            self.playback_tempo_enabled, self.source_bpm, self.target_bpm
        )

        # Return the new playback ratio for convenience
        return self.get_playback_ratio()

    def cut_audio(self, start_sample: int, end_sample: int) -> bool:
        """Trim audio to the region between start_sample and end_sample"""
        try:
            # DEBUG: Print detailed information about the cut operation
            if self.data_left is None:
                logger.warning("Error: data_left is None or doesn't exist")
                return False
                
            try:
                old_length = len(self.data_left)
                old_time_length = len(self.time) if self.time is not None else 0
                old_total_time = self.total_time
            except TypeError:
                logger.warning("Error: TypeError when accessing data length in cut_audio")
                return False
            
            logger.debug("\n==== AUDIO PROCESSOR CUT OPERATION ====")
            logger.debug("Current data state: samples=%s, time_length=%s, total_time=%s", old_length, old_time_length, old_total_time)
            
            # Ensure valid range
            try:
                data_length = len(self.data_left)
                if start_sample < 0:
                    logger.debug("Clamping start_sample from %s to 0", start_sample)
                    start_sample = 0
                if end_sample > data_length:
                    logger.debug("DEBUG: Clamping end_sample from %s to %s")
                    end_sample = data_length
            except TypeError:
                logger.warning("Error: TypeError when ensuring valid range in cut_audio")
                return False
            if start_sample >= end_sample:
                logger.debug("Invalid cut range: start_sample (%s) >= end_sample (%s)", start_sample, end_sample)
                return False
            
            logger.debug("DEBUG: Final cut range: start_sample=%s, end_sample=%s, new_length=%s")
                
            # Extract the selected portion of both channels
            trimmed_left = self.data_left[start_sample:end_sample]
            trimmed_right = self.data_right[start_sample:end_sample]
            
            # Update the audio data
            self.data_left = trimmed_left
            self.data_right = trimmed_right
            
            # Update total time based on new length
            old_total_time = self.total_time
            try:
                if self.data_left is not None:
                    self.total_time = len(self.data_left) / self.sample_rate
                else:
                    logger.warning("Error: data_left is None when updating total_time")
                    return False
                
                # Update time array
                try:
                    old_time_max = self.time[-1] if (self.time is not None and len(self.time) > 0) else None
                except TypeError:
                    logger.warning("WARNING: TypeError when accessing old_time_max in cut_audio")
                    old_time_max = None
                    
                self.time = np.linspace(0, self.total_time, len(self.data_left))
                
                try:
                    new_time_max = self.time[-1] if self.time is not None and len(self.time) > 0 else None
                except TypeError:
                    logger.warning("WARNING: TypeError when accessing new_time_max in cut_audio")
                    new_time_max = None
            except TypeError:
                logger.warning("Error: TypeError when updating time data in cut_audio")
                return False
            
            # Clear segments since they're now invalid - reset to single segment
            total_samples = len(self.data_left)
            self.segment_manager.set_audio_context(total_samples, self.sample_rate)
            
            # UPDATE AUDIO ENGINE with new source data
            self.audio_engine.set_source_audio(
                self.data_left, self.data_right, self.sample_rate, self.is_stereo
            )

            # DEBUG: Print detailed information about the result
            logger.debug("Cut operation: start=%s, end=%s, length=%s", start_sample, end_sample, end_sample-start_sample)
            logger.debug("DEBUG:   - Old total_time: %s, New total_time: %s", old_total_time, self.total_time)
            try:
                if self.data_left is not None:
                    logger.debug("DEBUG:   - New data length: %s", len(self.data_left))
                else:
                    logger.debug("DEBUG:   - New data_left is None")

                if self.time is not None:
                    logger.debug("DEBUG:   - New time length: %s", len(self.time))
                    if len(self.time) > 0:
                        logger.debug("DEBUG:   - New time range: [%s, %s]", self.time[0], self.time[-1])
                    else:
                        logger.debug("DEBUG:   - New time array is empty")
                else:
                    logger.debug("DEBUG:   - New time is None")
            except TypeError:
                logger.debug("WARNING: TypeError when printing debug info in cut_audio")
            logger.debug("==== END AUDIO PROCESSOR CUT OPERATION ====\n")

            return True
        except Exception as e:
            ErrorHandler.log_exception(e, context="WavAudioProcessor.cut_audio")
            return False

    def crop_to_time_range(self, start_time: float, end_time: float) -> bool:
        """Crop audio to a time range (convenience wrapper for cut_audio).

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            bool: True if successful, False otherwise
        """
        # Convert times to sample indices
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)

        logger.info("Cropping audio from %ss to %ss (samples %s to %s)",
                   start_time, end_time, start_sample, end_sample)

        return self.cut_audio(start_sample, end_sample)

    def convert_to_mono(self, method: str) -> bool:
        """Convert stereo audio to mono using specified method.

        Args:
            method: Conversion method - 'left', 'right', or 'mix'

        Returns:
            bool: True if converted successfully, False if already mono
        """
        # Check if already mono
        if not self.is_stereo:
            logger.info("Audio is already mono, no conversion needed")
            return False

        logger.info("Converting stereo to mono using '%s' method", method)

        # Apply conversion based on method
        if method == 'left':
            # Use left channel for both channels
            self.data_right = self.data_left.copy()
        elif method == 'right':
            # Use right channel for both channels
            self.data_left = self.data_right.copy()
        elif method == 'mix':
            # Average both channels
            mixed = (self.data_left + self.data_right) / 2.0
            self.data_left = mixed
            self.data_right = mixed.copy()
        else:
            logger.warning("Invalid mono conversion method: %s", method)
            return False

        # Update flags
        self.is_stereo = False
        self.channels = 1

        # Update audio engine with new data
        self.audio_engine.set_source_audio(
            self.data_left, self.data_right, self.sample_rate, self.is_stereo
        )

        logger.info("Successfully converted to mono (method=%s)", method)
        return True
