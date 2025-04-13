import numpy as np
import soundfile as sf
import sounddevice as sd
import librosa
import os
import pathlib
import sys
import threading
from config_manager import config

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
        pt_config = config.get_value_from_json_file("audio.json", "playbackTempo", {})
        
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
        samples_per_measure = len(self.data_left) // num_measures
        samples_per_slice = samples_per_measure // measure_resolution
        self.segments = [i * samples_per_slice for i in range(1, num_measures * measure_resolution)]
        return self.segments

    def split_by_transients(self, threshold=None):
        # Get transient detection parameters from config
        td_config = config.get_value_from_json_file("audio.json", "transientDetection", {})
        
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
        print(f"AudioProcessor.remove_segment({click_time})")
        print(f"Current segments: {self.segments}")
        if not self.segments:
            print("No segments to remove")
            return
        try:
            click_sample = int(click_time * self.sample_rate)
            print(f"Looking for segment near sample {click_sample}")
            closest_index = min(range(len(self.segments)),
                                key=lambda i: abs(self.segments[i] - click_sample))
            print(f"Found closest segment at index {closest_index}, value {self.segments[closest_index]}")
            del self.segments[closest_index]
            print(f"Successfully removed segment. Remaining segments: {self.segments}")
        except Exception as e:
            print(f"ERROR in remove_segment: {e}")
            import traceback
            traceback.print_exc()

    def add_segment(self, click_time):
        print(f"AudioProcessor.add_segment({click_time})")
        try:
            new_segment = int(click_time * self.sample_rate)
            print(f"Adding segment at sample {new_segment}")
            self.segments.append(new_segment)
            self.segments.sort()
            print(f"Successfully added segment. Current segments: {self.segments}")
        except Exception as e:
            print(f"ERROR in add_segment: {e}")
            import traceback
            traceback.print_exc()

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

    def play_segment(self, start_time, end_time):
        """Play a segment of audio in a non-blocking way, with toggle support"""
        print(f"### Model play_segment called with start_time={start_time}, end_time={end_time}")
        
        # If already playing, stop the current playback
        if self.is_playing:
            print("### Model already playing, stopping playback")
            self.stop_playback()
            return False  # Indicate that we stopped playback instead of starting it
        
        # Extract the segment data
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)
        print(f"### Converting to samples: start_sample={start_sample}, end_sample={end_sample}")
        
        # Validate sample range
        if start_sample < 0 or end_sample > len(self.data_left) or start_sample >= end_sample:
            print(f"### INVALID SAMPLE RANGE: start_sample={start_sample}, end_sample={end_sample}, data_length={len(self.data_left)}")
            return False
            
        # Create stereo segment if needed
        if self.is_stereo:
            print("### Creating stereo segment")
            left_segment = self.data_left[start_sample:end_sample]
            right_segment = self.data_right[start_sample:end_sample]
            segment = np.column_stack((left_segment, right_segment))
        else:
            print("### Creating mono segment")
            segment = self.data_left[start_sample:end_sample]
        
        print(f"### Segment created with shape: {segment.shape}")
        
        # Get the sample rate to use for playback (adjusted or original)
        playback_sample_rate = self.sample_rate
        if self.playback_tempo_enabled:
            playback_sample_rate = self.get_adjusted_sample_rate()
            print(f"### Using tempo-adjusted sample rate: {playback_sample_rate} Hz")
        
        # Define the playback function for threading
        def play_audio():
            try:
                print(f"### Starting playback thread for segment {start_time:.2f}s to {end_time:.2f}s")
                if self.playback_tempo_enabled:
                    ratio = self.get_playback_ratio()
                    print(f"### Tempo adjustment active: {ratio:.2f}x ({self.source_bpm:.1f} → {self.target_bpm} BPM)")
                    
                self.is_playing = True
                
                # Use the adjusted sample rate
                sd.play(segment, playback_sample_rate)
                sd.wait()  # This blocks until playback is complete
                print("### Playback complete")
            except Exception as e:
                print(f"### ERROR during playback: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.is_playing = False
                # Notify that playback has completed
                # Since we can't use QTimer from a thread, we'll set a flag
                # that can be checked by the main UI thread
                print("### Playback thread exiting")
                # Set a flag to indicate playback has ended
                self.playback_just_ended = True
        
        # Start playback in a separate thread
        print("### Creating playback thread")
        self.playback_thread = threading.Thread(target=play_audio)
        self.playback_thread.daemon = True  # Thread will exit when main program exits
        self.playback_thread.start()
        print("### Playback thread started")
        return True  # Indicate that we started playback
        
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
        if not hasattr(self, 'total_time') or self.total_time <= 0:
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
            
        if not hasattr(self, 'source_bpm') or self.source_bpm <= 0:
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
        if not hasattr(self, 'source_bpm') or self.source_bpm <= 0:
            self.calculate_source_bpm()
            
        print(f"Playback tempo updated: {self.playback_tempo_enabled}, "
              f"target={self.target_bpm} BPM, source={self.source_bpm:.2f} BPM")
        
        # Return the new playback ratio for convenience
        return self.get_playback_ratio()
        
    def cut_audio(self, start_sample, end_sample):
        """Trim audio to the region between start_sample and end_sample"""
        try:
            # Ensure valid range
            data_length = len(self.data_left)
            if start_sample < 0:
                start_sample = 0
            if end_sample > data_length:
                end_sample = data_length
            if start_sample >= end_sample:
                return False
                
            # Extract the selected portion of both channels
            trimmed_left = self.data_left[start_sample:end_sample]
            trimmed_right = self.data_right[start_sample:end_sample]
            
            # Update the audio data
            self.data_left = trimmed_left
            self.data_right = trimmed_right
            
            # Update total time based on new length
            self.total_time = len(self.data_left) / self.sample_rate
            
            # Update time array
            self.time = np.linspace(0, self.total_time, len(self.data_left))
            
            # Clear segments since they're now invalid
            self.segments = []
            
            return True
        except Exception as e:
            print(f"Error in cut_audio: {e}")
            return False
