import numpy as np
import soundfile as sf
import sounddevice as sd
import librosa
import os
import pathlib
import sys
from config_manager import config

class WavAudioProcessor:
    def __init__(self,
                 duration = 2.0,
                 sample_rate=44100,
                 preset_id='amen_classic'):
        self.segments = []
        self.preset_id = preset_id
        self.preset_info = None
        
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
        self.filename = filename
        with sf.SoundFile(filename) as sound_file:
            self.sample_rate = sound_file.samplerate
            self.total_time = len(sound_file) / self.sample_rate
        self.time = np.linspace(0, self.total_time, int(self.total_time * self.sample_rate))
        self.data = self._generate_data()
        self.segments = []

    def _generate_data(self) -> np.ndarray:
        audio_data, _ = sf.read(self.filename, always_2d=True)
        if audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)
        else:
            audio_data = audio_data.flatten()
        return audio_data

    def get_data(self, start_time: float, end_time: float) -> tuple[np.ndarray, np.ndarray]:
        start_idx = int(start_time * self.sample_rate)
        end_idx = int(end_time * self.sample_rate)
        return self.time[start_idx:end_idx], self.data[start_idx:end_idx]

    def get_tempo(self, num_bars: int,
                        beats_per_bar: int = 4) -> float:
        total_beats = num_bars * beats_per_bar
        total_time_minutes = self.total_time / 60
        tempo = total_beats / total_time_minutes
        return tempo

    def split_by_bars(self, num_bars, bar_resolution):
        samples_per_bar = len(self.data) // num_bars
        samples_per_slice = samples_per_bar // bar_resolution
        self.segments = [i * samples_per_slice for i in range(1, num_bars * bar_resolution)]
        return self.segments

    def split_by_transients(self, threshold=0.2):
        print(f"split_by_transients: {threshold}")
        delta = threshold * 0.1
        onset_env = librosa.onset.onset_strength(y=self.data, sr=self.sample_rate)
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
        for i, segment in enumerate(segments):
            if click_sample < segment:
                if i == 0:
                    return 0, segment / self.sample_rate
                else:
                    return segments[i-1] / self.sample_rate, segment / self.sample_rate
        if segments:
            return segments[-1] / self.sample_rate, len(self.data) / self.sample_rate
        else:
            return 0, len(self.data) / self.sample_rate

    def play_segment(self, start_time, end_time):
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)
        segment = self.data[start_sample:end_sample]
        sd.play(segment, self.sample_rate)
        sd.wait()

    def get_sample_at_time(self, time):
        return int(time * self.sample_rate)
        
    def cut_audio(self, start_sample, end_sample):
        """Trim audio to the region between start_sample and end_sample"""
        try:
            # Ensure valid range
            if start_sample < 0:
                start_sample = 0
            if end_sample > len(self.data):
                end_sample = len(self.data)
            if start_sample >= end_sample:
                return False
                
            # Extract the selected portion
            trimmed_data = self.data[start_sample:end_sample]
            
            # Update the audio data
            self.data = trimmed_data
            
            # Update total time based on new length
            self.total_time = len(self.data) / self.sample_rate
            
            # Update time array
            self.time = np.linspace(0, self.total_time, len(self.data))
            
            # Clear segments since they're now invalid
            self.segments = []
            
            return True
        except Exception as e:
            print(f"Error in cut_audio: {e}")
            return False
