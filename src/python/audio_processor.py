import numpy as np
import soundfile as sf
import librosa
import os
import pathlib
import sys
from config_manager import config
from error_handler import ErrorHandler

# Import the high-performance audio engine
from high_performance_audio import ImprovedAudioEngine, PlaybackMode

# Import audio processing functions from shared utils
from audio_utils import (
    extract_segment, apply_playback_tempo, resample_to_standard_rate,
    apply_tail_fade, reverse_segment, process_segment_for_output
)


class WavAudioProcessor:
    def __init__(self,
                 duration = 2.0,
                 sample_rate=44100,
                 preset_id='amen_classic'):
        self.segments = []
        self.preset_id = preset_id
        self.preset_info = None
        self.is_playing = False
        self.playback_just_ended = False  # Flag to indicate playback has just ended
        self.is_stereo = False
        self.channels = 1
        
        # Initialize high-performance audio engine
        print("Using high-performance audio engine")
        self.audio_engine = ImprovedAudioEngine(
            sample_rate=sample_rate,
            channels=2,  # Always use stereo for compatibility
            blocksize=512  # Low latency block size
        )
        self.audio_engine.set_playback_ended_callback(self._on_playback_ended)
        
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
    
    def _on_playback_ended(self):
        """Callback from audio engine when playback ends"""
        self.playback_just_ended = True
        self.is_playing = False

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
        # DJP: refactor this chained function to break out for set_filename,
        #      initialize_audio_buffer,
        #      set_measures and calculate_source_bpm
        try:
            self.filename = filename
            with sf.SoundFile(filename) as sound_file:
                self.sample_rate = sound_file.samplerate
                self.channels = sound_file.channels
                self.is_stereo = self.channels > 1
                self.total_time = len(sound_file) / self.sample_rate
                
            self.data_left, self.data_right = self._generate_data()
            
            # Create time array based on the actual data length
            self.time = np.linspace(0, self.total_time, len(self.data_left))
            self.segments = []
            
            # Initialize audio engine with source data
            self.audio_engine.set_source_audio(
                self.data_left, self.data_right, self.sample_rate, self.is_stereo
            )
            self.audio_engine.start_stream()
            
            # Calculate source BPM based on the loaded audio file and preset measures
            # Use the 'measures' field from preset_info if available
            measures = None
            try:
                measures = self.preset_info.get('measures', None)
            except Exception:
                measures = None
            # Fallback to 1 measure if not specified
            if measures is None:
                measures = 1
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
        print(f"\n----- DETAILED GET_TEMPO CALCULATION -----")
        print(f"File: {self.filename}")
        print(f"Input num_measures: {num_measures}")
        print(f"Beats per measure: {beats_per_measure}")
        print(f"Total time: {self.total_time:.6f}s = {self.total_time/60:.6f} minutes")
        
        total_beats = num_measures * beats_per_measure
        print(f"Total beats: {num_measures} × {beats_per_measure} = {total_beats}")
        
        total_time_minutes = self.total_time / 60
        tempo = total_beats / total_time_minutes
        
        print(f"Tempo calculation: {total_beats} beats / {total_time_minutes:.6f} minutes = {tempo:.2f} BPM")
        print(f"----- END GET_TEMPO CALCULATION -----\n")
        
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
        """Play a segment of audio using the high-performance engine
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            reverse: Whether to play the segment in reverse
        
        Returns:
            bool: True if playback started, False otherwise
        """
        print(f"### Model play_segment called with start_time={start_time}, end_time={end_time}, reverse={reverse}")
        print(f"### High-performance play: {start_time:.2f}s to {end_time:.2f}s, reverse={reverse}")
        
        # Update engine settings
        self.audio_engine.set_playback_tempo(
            self.playback_tempo_enabled, self.source_bpm, self.target_bpm
        )
        
        # Play the segment
        self.is_playing = True
        return self.audio_engine.play_segment(start_time, end_time, reverse)
        
    def stop_playback(self):
        """Stop any currently playing audio"""
        self.audio_engine.stop_playback()
        self.is_playing = False

    def get_sample_at_time(self, time):
        return int(time * self.sample_rate)
    
    def calculate_source_bpm(self, measures=None):
        """Calculate source BPM based on audio duration and measure count
        
        Formula: Source BPM = (60 × beats) / duration
        Where beats = measures × 4 (assuming 4/4 time signature)
        
        Returns:
            float: The calculated BPM value (self.source_bpm)
        """
        print("\n===== DETAILED BPM CALCULATION DEBUGGING =====")
        print(f"Input measures value: {measures}")
        print(f"File: {self.filename}")
        print(f"Total time: {self.total_time:.6f}s")
        
        if self.total_time <= 0:
            print("WARNING: Cannot calculate source BPM, invalid duration")
            self.source_bpm = 120.0  # Default fallback
            print(f"Using default BPM: {self.source_bpm}")
            return self.source_bpm
            
        # Get beats per measure from config (default to 4/4 time signature)
        beats_per_measure = 4  # Standard 4/4 time for breakbeats
        print(f"Using beats_per_measure: {beats_per_measure}")
        
        # Calculate total beats in the audio file
        total_beats = measures * beats_per_measure
        print(f"Total beats: {measures} × {beats_per_measure} = {total_beats}")
        
        # Calculate BPM based on total beats
        old_source_bpm = getattr(self, 'source_bpm', None)
        self.source_bpm = (60.0 * total_beats) / self.total_time
        
        print(f"BPM CALCULATION: ({60.0} × {total_beats}) / {self.total_time} = {self.source_bpm:.2f} BPM")
        if old_source_bpm is not None:
            print(f"     Changed from {old_source_bpm:.2f} to {self.source_bpm:.2f} BPM")
            
        print(f"Final source BPM: {self.source_bpm:.2f} BPM")
        print("===== END DETAILED BPM CALCULATION =====\n")
        
        return self.source_bpm
    
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
        
        # Update audio engine immediately with new tempo settings
        self.audio_engine.set_playback_tempo(
            self.playback_tempo_enabled, self.source_bpm, self.target_bpm
        )
        
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
            
            # UPDATE AUDIO ENGINE with new source data
            self.audio_engine.set_source_audio(
                self.data_left, self.data_right, self.sample_rate, self.is_stereo
            )
            
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
            print(f"DEBUG:   - Audio engine updated with new source data")
            print(f"==== END AUDIO PROCESSOR CUT OPERATION ====\n")
            
            return True
        except Exception as e:
            ErrorHandler.log_exception(e, context="WavAudioProcessor.cut_audio")
            return False
