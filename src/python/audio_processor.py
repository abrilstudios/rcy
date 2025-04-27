import numpy as np
import soundfile as sf
import sounddevice as sd
import librosa
import os
import pathlib
import sys
import threading
from config_manager import config
from error_handler import ErrorHandler

# Audio Processing Pipeline Functions

def extract_segment(data_left, data_right, start_sample, end_sample, is_stereo=False):
    """Extract a slice of audio from source data
    
    Args:
        data_left: Left channel audio data
        data_right: Right channel audio data (same as left for mono)
        start_sample: Start sample index
        end_sample: End sample index
        is_stereo: Whether to create a stereo segment
        
    Returns:
        np.ndarray: Audio segment (mono or stereo)
    """
    # Validate sample range
    if start_sample < 0 or start_sample >= len(data_left) or end_sample > len(data_left):
        raise ValueError(f"Invalid sample range: {start_sample} to {end_sample}, data length: {len(data_left)}")
    
    # Ensure start < end
    if start_sample >= end_sample:
        raise ValueError(f"Start sample must be less than end sample: {start_sample} >= {end_sample}")
    
    # Extract segment based on stereo/mono
    if is_stereo:
        left_segment = data_left[start_sample:end_sample]
        right_segment = data_right[start_sample:end_sample]
        segment = np.column_stack((left_segment, right_segment))
    else:
        segment = data_left[start_sample:end_sample]
    
    return segment

def apply_playback_tempo(segment, original_sample_rate, source_bpm, target_bpm, enabled=True):
    """Apply tempo adjustment via sample rate modification
    
    Args:
        segment: Audio segment data (mono or stereo)
        original_sample_rate: Original sample rate of the audio
        source_bpm: Source BPM of the audio
        target_bpm: Target BPM for playback
        enabled: Whether tempo adjustment is enabled
        
    Returns:
        tuple: (segment, adjusted_sample_rate)
    """
    # Return original if not enabled or invalid BPM values
    if not enabled or target_bpm is None or source_bpm is None or source_bpm <= 0:
        return segment, original_sample_rate
    
    # Calculate the tempo ratio
    tempo_ratio = target_bpm / source_bpm
    
    # Calculate the adjusted sample rate
    adjusted_sample_rate = int(original_sample_rate * tempo_ratio)
    
    return segment, adjusted_sample_rate

def resample_to_standard_rate(segment, adjusted_sample_rate, target_sample_rate=44100, is_stereo=False):
    """Resample audio from adjusted sample rate back to standard rate
    
    This function resamples audio that has been pitch-shifted via sample rate adjustment
    back to a standard sample rate (default 44100 Hz), making it compatible with 
    samplers and DAWs while preserving the pitch shift.
    
    Args:
        segment: Audio segment data (mono or stereo)
        adjusted_sample_rate: Current sample rate of the audio (after tempo adjustment)
        target_sample_rate: Standard sample rate to resample to (default 44100 Hz)
        is_stereo: Whether the segment is stereo (2 channels)
        
    Returns:
        np.ndarray: Resampled audio segment at target_sample_rate
    """
    # No need to resample if rates are nearly identical
    if abs(adjusted_sample_rate - target_sample_rate) < 1.0:
        return segment
    
    # Handle stereo audio (resample each channel separately)
    if is_stereo:
        # Get left and right channels
        left_channel = segment[:, 0]
        right_channel = segment[:, 1]
        
        # Resample each channel
        left_resampled = librosa.resample(
            left_channel, 
            orig_sr=adjusted_sample_rate, 
            target_sr=target_sample_rate,
            res_type='kaiser_fast'  # Faster method that's still good quality
        )
        
        right_resampled = librosa.resample(
            right_channel, 
            orig_sr=adjusted_sample_rate, 
            target_sr=target_sample_rate,
            res_type='kaiser_fast'
        )
        
        # Recombine channels
        resampled = np.column_stack((left_resampled, right_resampled))
    else:
        # Mono audio resampling
        resampled = librosa.resample(
            segment, 
            orig_sr=adjusted_sample_rate, 
            target_sr=target_sample_rate,
            res_type='kaiser_fast'  # Faster method that's still good quality
        )
    
    return resampled

def apply_tail_fade(segment, sample_rate, is_stereo=False, enabled=False, duration_ms=10, curve="exponential"):
    """Apply fade-out at the end of a segment
    
    Args:
        segment: Audio segment data (mono or stereo)
        sample_rate: Sample rate of the audio
        is_stereo: Whether segment is stereo (2 channels)
        enabled: Whether fade is enabled
        duration_ms: Duration of fade in milliseconds
        curve: Type of fade curve ("linear" or "exponential")
        
    Returns:
        np.ndarray: Audio segment with fade applied
    """
    # Return original if not enabled or invalid duration
    if not enabled or duration_ms <= 0:
        return segment
    
    # Make a copy to avoid modifying the original
    processed = segment.copy()
    
    # Convert ms to samples
    fade_length_samples = int((duration_ms / 1000) * sample_rate)
    
    # Ensure fade length isn't longer than the segment
    if fade_length_samples > processed.shape[0]:
        fade_length_samples = processed.shape[0]
    
    if fade_length_samples > 0:
        # Create fade curve (from 1.0 to 0.0)
        if curve == "exponential":
            # Create a curve that drops off more quickly (exponential)
            # Using a higher power makes the curve more pronounced
            fade_curve_values = np.linspace(0, 1, fade_length_samples) ** 3
            # Invert so it goes from 1 to 0
            fade_curve_values = 1 - fade_curve_values
        else:  # Linear fade
            fade_curve_values = np.linspace(1, 0, fade_length_samples)
        
        # Apply fade to end of segment
        if is_stereo:
            # Apply to both channels
            start_idx = processed.shape[0] - fade_length_samples
            processed[start_idx:, 0] *= fade_curve_values
            processed[start_idx:, 1] *= fade_curve_values
        else:
            # Apply to mono
            start_idx = processed.shape[0] - fade_length_samples
            processed[start_idx:] *= fade_curve_values
    
    return processed

def reverse_segment(segment, is_stereo=False):
    """Reverse an audio segment
    
    Args:
        segment: Audio segment data (mono or stereo)
        is_stereo: Whether segment is stereo (2 channels)
        
    Returns:
        np.ndarray: Reversed audio segment
    """
    # Make a copy to avoid modifying the original
    processed = segment.copy()
    
    if is_stereo:
        # For stereo audio, we need to flip the rows but keep columns intact
        return np.flipud(processed)
    else:
        # For mono audio, just flip the array
        return np.flip(processed)

def process_segment_for_output(
    data_left,
    data_right,
    start_sample,
    end_sample,
    sample_rate=44100,
    is_stereo=False,
    reverse=False,
    playback_tempo_enabled=False,
    source_bpm=None,
    target_bpm=None,
    tail_fade_enabled=False,
    fade_duration_ms=10,
    fade_curve="exponential",
    for_export=False,
    resample_on_export=True
):
    """Process audio segment through the complete pipeline for output
    
    This function orchestrates the full pipeline:
    1. Extract segment from source data
    2. Apply reverse if needed
    3. Apply playback tempo adjustment
    4. Resample to standard rate (if for_export=True and resample_on_export=True)
    5. Apply tail fade if enabled
    
    Args:
        data_left: Left channel audio data
        data_right: Right channel audio data (same as left for mono)
        start_sample: Start sample index 
        end_sample: End sample index
        sample_rate: Sample rate of the audio
        is_stereo: Whether to create a stereo segment
        reverse: Whether to reverse the segment
        playback_tempo_enabled: Whether tempo adjustment is enabled
        source_bpm: Source BPM of the audio
        target_bpm: Target BPM for playback
        tail_fade_enabled: Whether to apply fade-out
        fade_duration_ms: Duration of fade in milliseconds
        fade_curve: Type of fade curve ("linear" or "exponential")
        for_export: Whether this processing is for export (vs. playback)
        resample_on_export: Whether to resample to standard rate on export
        
    Returns:
        tuple: (processed_segment, output_sample_rate)
    """
    # Stage 1: Extract the segment
    segment = extract_segment(
        data_left, data_right, start_sample, end_sample, is_stereo
    )
    
    # Stage 2: Apply reverse if needed
    if reverse:
        segment = reverse_segment(segment, is_stereo)
    
    # Stage 3: Apply playback tempo adjustment
    segment, adjusted_sample_rate = apply_playback_tempo(
        segment, sample_rate, source_bpm, target_bpm, playback_tempo_enabled
    )
    
    # Store the original adjusted rate for return value
    output_sample_rate = adjusted_sample_rate
    
    # Stage 4: Resample to standard sample rate if for export
    if for_export and resample_on_export and playback_tempo_enabled:
        # Only resample if tempo adjustment was actually applied
        if adjusted_sample_rate != sample_rate:
            segment = resample_to_standard_rate(
                segment, adjusted_sample_rate, sample_rate, is_stereo
            )
            # For export, we'll use the original sample rate in the WAV header
            output_sample_rate = sample_rate
    
    # Stage 5: Apply tail fade
    segment = apply_tail_fade(
        segment, adjusted_sample_rate, is_stereo, tail_fade_enabled, fade_duration_ms, fade_curve
    )
    
    return segment, output_sample_rate

class WavAudioProcessor:
    def __init__(self,
                 duration = 2.0,
                 sample_rate=44100,
                 preset_id='amen_classic'):
        self.segments = []
        self.preset_id = preset_id
        self.preset_info = None
        self.is_playing = False
        self.playback_thread = None
        self.playback_just_ended = False  # Flag to indicate playback has just ended
        self.is_stereo = False
        self.channels = 1
        
        # Initialize playback tempo settings
        self._init_playback_tempo()
        
        # Try to load the specified preset
        try:
            self.load_preset(preset_id)
        except Exception as e:
            print(f"ERROR: Failed to load preset '{preset_id}': {e}")
            sys.exit(1)
    
    def _init_playback_tempo(self):
        """Initialize playback tempo settings from config"""
        # Get playback tempo config with defaults
        pt_config = config.get_setting("audio", "playbackTempo", {})
        
        # Read settings with defaults
        self.playback_tempo_enabled = pt_config.get("enabled", False)
        self.target_bpm = int(pt_config.get("targetBpm", 120))
        
        # Source BPM is calculated from audio duration and measures
        # Will be set properly after loading preset
        self.source_bpm = 120.0  # Default value
        
        print(f"Playback tempo initialized: {self.playback_tempo_enabled}, "
              f"target={self.target_bpm} BPM")

    def load_preset(self, preset_id):
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
        try:
            self.filename = filename
            with sf.SoundFile(filename) as sound_file:
                self.sample_rate = sound_file.samplerate
                self.channels = sound_file.channels
                self.is_stereo = self.channels > 1
                self.total_time = len(sound_file) / self.sample_rate
                
            self.data_left, self.data_right = self._generate_data()
            
            # Ensure both left and right channels have the same length
            if len(self.data_left) != len(self.data_right):
                min_length = min(len(self.data_left), len(self.data_right))
                self.data_left = self.data_left[:min_length]
                self.data_right = self.data_right[:min_length]
                # Update total time based on the corrected data length
                self.total_time = min_length / self.sample_rate
                print(f"Warning: Channels had different lengths. Truncated to {min_length} samples.")
                
            # Create time array based on the actual data length
            self.time = np.linspace(0, self.total_time, len(self.data_left))
            self.segments = []
            
            # Calculate source BPM based on the loaded audio file
            measures = None  # Use the value from preset_info
            self.calculate_source_bpm(measures=measures)
        except Exception as e:
            print(f"Error loading audio file {filename}: {e}")
            raise

    def _generate_data(self) -> tuple[np.ndarray, np.ndarray]:
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
                print(f"Warning: Channels had different lengths. Truncated to {min_length} samples.")
        else:
            # Mono file - duplicate the channel for consistency in code
            data_left = audio_data.flatten()
            data_right = data_left.copy()
            
        return data_left, data_right

    def get_data(self, start_time: float, end_time: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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

    def get_tempo(self, num_measures: int,
                        beats_per_measure: int = 4) -> float:
        total_beats = num_measures * beats_per_measure
        total_time_minutes = self.total_time / 60
        tempo = total_beats / total_time_minutes
        return tempo

    def split_by_measures(self, num_measures, measure_resolution):
        """Split audio into equal divisions based on musical measures
        
        Args:
            num_measures: Number of musical measures in the audio
            measure_resolution: Number of divisions per measure
        
        Returns:
            List of sample positions for the segments
        
        For example, with 2 measures and resolution 4:
        - We should create 8 segments (2 measures × 4 divisions)
        - This requires 9 slice points (to define the 8 segments)
        """
        # Get total samples and calculate division sizes
        total_samples = len(self.data_left)
        total_divisions = num_measures * measure_resolution
        samples_per_division = total_samples / total_divisions
        
        # Create segment points including start and end
        # This gives num_measures * measure_resolution + 1 points
        # For 2 measures with resolution 4, this gives 9 points (0, 1/8, 2/8, ..., 8/8)
        self.segments = [int(i * samples_per_division) for i in range(total_divisions + 1)]
        
        # Ensure last point is exactly at the end of the audio
        if self.segments[-1] != total_samples:
            self.segments[-1] = total_samples
            
        return self.segments

    def split_by_transients(self, threshold=None):
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
        
        print(f"split_by_transients: threshold={threshold}, wait={wait_time}, "
              f"pre_max={pre_max}, post_max={post_max}, delta={delta}")
        
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
        onset_samples = librosa.frames_to_samples(onsets)
        self.segments = onset_samples.tolist()
        return self.segments

    def remove_segment(self, click_time):
        """Remove the segment closest to click_time."""
        try:
            if not self.segments:
                raise ValueError("No segments to remove")
            click_sample = int(click_time * self.sample_rate)
            closest_index = min(range(len(self.segments)),
                                key=lambda i: abs(self.segments[i] - click_sample))
            del self.segments[closest_index]
        except Exception as e:
            ErrorHandler.log_exception(e, context="WavAudioProcessor.remove_segment")
            return

    def add_segment(self, click_time):
        """Add a new segment at click_time."""
        try:
            new_segment = int(click_time * self.sample_rate)
            self.segments.append(new_segment)
            self.segments.sort()
        except Exception as e:
            ErrorHandler.log_exception(e, context="WavAudioProcessor.add_segment")
            return

    def get_segments(self):
        return self.segments

    def get_segment_boundaries(self, click_time):
        click_sample = int(click_time * self.sample_rate)
        segments = self.get_segments()
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

    def play_segment(self, start_time, end_time, reverse=False):
        """Play a segment of audio in a non-blocking way, with toggle support
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            reverse: Whether to play the segment in reverse
        
        Returns:
            bool: True if playback started, False otherwise
        """
        print(f"### Model play_segment called with start_time={start_time}, end_time={end_time}, reverse={reverse}")
        
        # If already playing, stop the current playback
        if self.is_playing:
            print("### Model already playing, stopping playback")
            self.stop_playback()
            return False  # Indicate that we stopped playback instead of starting it
        
        # Always ensure start_time < end_time for sample extraction
        # We'll handle reverse playback by reversing the segment data
        if start_time > end_time:
            print(f"### Swapping start/end times: {start_time} > {end_time}")
            start_time, end_time = end_time, start_time
            
        # Extract the segment data
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)
        print(f"### Converting to samples: start_sample={start_sample}, end_sample={end_sample}")
        
        try:
            # Get tail fade settings from config
            tail_fade_config = config.get_setting("audio", "tailFade", {})
            tail_fade_enabled = tail_fade_config.get("enabled", False)
            fade_duration_ms = tail_fade_config.get("durationMs", 10)
            fade_curve = tail_fade_config.get("curve", "exponential")
            
            # Process the segment through our pipeline (for playback, not export)
            segment, playback_sample_rate = process_segment_for_output(
                self.data_left,
                self.data_right,
                start_sample,
                end_sample,
                self.sample_rate,
                self.is_stereo,
                reverse,
                self.playback_tempo_enabled,
                self.source_bpm,
                self.target_bpm,
                tail_fade_enabled,
                fade_duration_ms,
                fade_curve,
                for_export=False,  # This is for playback, not export
                resample_on_export=True  # Not used since for_export is False
            )
            
            print(f"### Segment processed with shape: {segment.shape}")
            
            if self.playback_tempo_enabled:
                ratio = self.get_playback_ratio()
                print(f"### Tempo adjustment active: {ratio:.2f}x ({self.source_bpm:.1f} → {self.target_bpm} BPM)")
                print(f"### Using tempo-adjusted sample rate: {playback_sample_rate} Hz")
            
            # Define the playback function for threading
            def play_audio():
                try:
                    print(f"### Starting playback thread for segment {start_time:.2f}s to {end_time:.2f}s")
                    print(f"### Direction: {'reverse' if reverse else 'forward'}")
                    
                    self.is_playing = True
                    
                    # Use the adjusted sample rate
                    sd.play(segment, playback_sample_rate)
                    sd.wait()  # This blocks until playback is complete
                    print("### Playback complete")
                except Exception as e:
                    ErrorHandler.log_exception(e, context="WavAudioProcessor.play_segment_thread")
                finally:
                    self.is_playing = False
                    # Set a flag to indicate playback has ended
                    print("### Playback thread exiting")
                    self.playback_just_ended = True
            
            # Start playback in a separate thread
            print("### Creating playback thread")
            self.playback_thread = threading.Thread(target=play_audio)
            self.playback_thread.daemon = True  # Thread will exit when main program exits
            self.playback_thread.start()
            print("### Playback thread started")
            return True  # Indicate that we started playback
            
        except Exception as e:
            ErrorHandler.log_exception(e, context="WavAudioProcessor.play_segment")
            return False
        
    def stop_playback(self):
        """Stop any currently playing audio"""
        if self.is_playing:
            sd.stop()
            self.is_playing = False
            
    # Removed _notify_playback_ended and set_playback_ended_callback methods
    # We now use the playback_just_ended flag checked by a timer in the controller
            # The thread will end naturally when sd.wait() is interrupted

    def get_sample_at_time(self, time):
        return int(time * self.sample_rate)
    
    def calculate_source_bpm(self, measures=None):
        """Calculate source BPM based on audio duration and measure count
        
        Formula: Source BPM = (60 × beats) / duration
        Where beats = measures × 4 (assuming 4/4 time signature)
        """
        if self.total_time <= 0:
            print("Warning: Cannot calculate source BPM, invalid duration")
            return 120.0  # Default fallback
            
        # Use provided measures or get from preset info
        if measures is None:
            if self.preset_info and 'measures' in self.preset_info:
                measures = self.preset_info.get('measures', 4)
            else:
                measures = 4  # Default if not specified
                
        # Ensure positive value
        if measures <= 0:
            measures = 4
            
        # Get beats per measure from config (default to 4/4 time signature)
        beats_per_measure = 4  # Standard 4/4 time for breakbeats
        
        # Calculate total beats in the audio file
        total_beats = measures * beats_per_measure
        
        # Calculate BPM based on total beats
        source_bpm = (60.0 * total_beats) / self.total_time
        
        # Store the calculated value
        self.source_bpm = source_bpm
        
        print(f"Calculated source BPM: {source_bpm:.2f} based on {measures} measures × {beats_per_measure} beats = {total_beats} beats over {self.total_time:.2f}s duration")
        return source_bpm
    
    def get_playback_ratio(self):
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
        
        print(f"Playback ratio: {ratio:.2f} (target: {self.target_bpm} BPM / source: {self.source_bpm:.2f} BPM)")
        return ratio
    
    def get_adjusted_sample_rate(self):
        """Get the sample rate adjusted for tempo change"""
        if not self.playback_tempo_enabled:
            return self.sample_rate
            
        # Calculate the playback ratio
        ratio = self.get_playback_ratio()
        
        # Apply ratio to sample rate
        adjusted_rate = int(self.sample_rate * ratio)
        
        print(f"Adjusted sample rate: {adjusted_rate} Hz (original: {self.sample_rate} Hz, ratio: {ratio:.2f})")
        return adjusted_rate
    
    def set_playback_tempo(self, enabled, target_bpm=None):
        """Configure playback tempo settings
        
        Args:
            enabled (bool): Whether tempo adjustment is enabled
            target_bpm (int, optional): Target tempo in BPM
        """
        self.playback_tempo_enabled = enabled
        
        if target_bpm is not None:
            self.target_bpm = int(target_bpm)
            
        # Ensure source BPM is calculated
        if self.source_bpm <= 0:
            self.calculate_source_bpm()
            
        print(f"Playback tempo updated: {self.playback_tempo_enabled}, "
              f"target={self.target_bpm} BPM, source={self.source_bpm:.2f} BPM")
        
        # Return the new playback ratio for convenience
        return self.get_playback_ratio()
        
    def cut_audio(self, start_sample, end_sample):
        """Trim audio to the region between start_sample and end_sample"""
        try:
            # DEBUG: Print detailed information about the cut operation
            if self.data_left is None:
                print("ERROR: data_left is None or doesn't exist")
                return False
                
            try:
                old_length = len(self.data_left)
                old_time_length = len(self.time) if self.time is not None else 0
                old_total_time = self.total_time
            except TypeError:
                print("ERROR: TypeError when accessing data length in cut_audio")
                return False
            
            print(f"\n==== AUDIO PROCESSOR CUT OPERATION ====")
            print(f"Cut request: start_sample={start_sample}, end_sample={end_sample}")
            print(f"Current data state: samples={old_length}, time_length={old_time_length}, total_time={old_total_time}")
            
            # Ensure valid range
            try:
                data_length = len(self.data_left)
                if start_sample < 0:
                    print(f"DEBUG: Clamping start_sample from {start_sample} to 0")
                    start_sample = 0
                if end_sample > data_length:
                    print(f"DEBUG: Clamping end_sample from {end_sample} to {data_length}")
                    end_sample = data_length
            except TypeError:
                print("ERROR: TypeError when ensuring valid range in cut_audio")
                return False
            if start_sample >= end_sample:
                print(f"DEBUG: Invalid cut range: start_sample({start_sample}) >= end_sample({end_sample})")
                return False
            
            print(f"DEBUG: Final cut range: start_sample={start_sample}, end_sample={end_sample}, new_length={end_sample-start_sample}")
                
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
                    print("ERROR: data_left is None when updating total_time")
                    return False
                
                # Update time array
                try:
                    old_time_max = self.time[-1] if (self.time is not None and len(self.time) > 0) else None
                except TypeError:
                    print("WARNING: TypeError when accessing old_time_max in cut_audio")
                    old_time_max = None
                    
                self.time = np.linspace(0, self.total_time, len(self.data_left))
                
                try:
                    new_time_max = self.time[-1] if self.time is not None and len(self.time) > 0 else None
                except TypeError:
                    print("WARNING: TypeError when accessing new_time_max in cut_audio")
                    new_time_max = None
            except TypeError:
                print("ERROR: TypeError when updating time data in cut_audio")
                return False
            
            # Clear segments since they're now invalid
            self.segments = []
            
            # DEBUG: Print detailed information about the result
            print(f"DEBUG: Cut operation result:")
            print(f"DEBUG:   - Old total_time: {old_total_time}, New total_time: {self.total_time}")
            print(f"DEBUG:   - Old time_max: {old_time_max}, New time_max: {new_time_max}")
            try:
                if self.data_left is not None:
                    print(f"DEBUG:   - New data length: {len(self.data_left)}")
                else:
                    print("DEBUG:   - New data_left is None")
                    
                if self.time is not None:
                    print(f"DEBUG:   - New time array length: {len(self.time)}")
                    if len(self.time) > 0:
                        print(f"DEBUG:   - New time range: [{self.time[0]}, {self.time[-1]}]")
                    else:
                        print("DEBUG:   - New time array is empty")
                else:
                    print("DEBUG:   - New time is None")
            except TypeError:
                print("WARNING: TypeError when printing debug info in cut_audio")
            print(f"==== END AUDIO PROCESSOR CUT OPERATION ====\n")
            
            return True
        except Exception as e:
            ErrorHandler.log_exception(e, context="WavAudioProcessor.cut_audio")
            return False
