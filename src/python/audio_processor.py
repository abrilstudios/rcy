import numpy as np
import soundfile as sf
import sounddevice as sd
import librosa
import os
import pathlib
import sys
import threading
from src.python.config_manager import config

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
        
        # Try to load the specified preset
        try:
            self.load_preset(preset_id)
        except Exception as e:
            print(f"ERROR: Failed to load preset '{preset_id}': {e}")
            sys.exit(1)

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

    def split_by_transients(self, threshold=0.2):
        print(f"split_by_transients: {threshold}")
        delta = threshold * 0.1
        # Use left channel for transient detection
        onset_env = librosa.onset.onset_strength(y=self.data_left, sr=self.sample_rate)
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env, 
            sr=self.sample_rate,
            delta=delta,
            wait=1,
            pre_max=1,
            post_max=1,
        )
        onset_samples = librosa.frames_to_samples(onsets)
        self.segments = onset_samples.tolist()
        return self.segments

    def remove_segment(self, click_time):
        print(f"remove_segment {click_time}")
        print(f"remove_segment {self.segments}")
        if not self.segments:
            return
        click_sample = int(click_time * self.sample_rate)
        print(f"remove_segment {click_sample}")
        closest_index = min(range(len(self.segments)),
                            key=lambda i: abs(self.segments[i] - click_sample))
        del self.segments[closest_index]

    def add_segment(self, click_time):
        print(f"remove_segment {click_time}")
        new_segment = int(click_time * self.sample_rate)
        self.segments.append(new_segment)
        self.segments.sort()

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
        
        # Define the playback function for threading
        def play_audio():
            try:
                print(f"### Starting playback thread for segment {start_time:.2f}s to {end_time:.2f}s")
                self.is_playing = True
                sd.play(segment, self.sample_rate)
                sd.wait()  # This blocks until playback is complete
                print("### Playback complete")
            except Exception as e:
                print(f"### ERROR during playback: {e}")
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
