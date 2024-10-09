import numpy as np
import soundfile as sf
from abc import ABC, abstractmethod

class AudioProcessor(ABC):
    """
    Abstract base class for audio processing.

    This class defines the interface for audio processors in the Recycle application.
    Subclasses should implement the _generate_data method to provide specific audio data.

    Attributes:
        total_time (float): The total duration of the audio in seconds.
        sample_rate (int): The number of samples per second.
        time (np.ndarray): An array of time points for the audio data.
        data (np.ndarray): The generated audio data.
    """

    def __init__(self, total_time: float, sample_rate: int):
        """
        Initialize the AudioProcessor.

        Args:
            total_time (float): The total duration of the audio in seconds.
            sample_rate (int): The number of samples per second.
        """
        self.total_time = total_time
        self.sample_rate = sample_rate
        self.time = np.linspace(0, total_time, int(total_time * sample_rate))
        self.data = self._generate_data()

    @abstractmethod
    def _generate_data(self) -> np.ndarray:
        """
        Generate the audio data.

        This method should be implemented by subclasses to generate the specific audio data.

        Returns:
            np.ndarray: The generated audio data.
        """
        pass

    def get_data(self, start_time: float, end_time: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Retrieve a segment of the audio data.

        Args:
            start_time (float): The start time of the segment in seconds.
            end_time (float): The end time of the segment in seconds.

        Returns:
            tuple[np.ndarray, np.ndarray]: A tuple containing two arrays:
                - The time points for the requested segment.
                - The audio data for the requested segment.
        """
        start_idx = int(start_time * self.sample_rate)
        end_idx = int(end_time * self.sample_rate)
        return self.time[start_idx:end_idx], self.data[start_idx:end_idx]


class SinAudioProcessor(AudioProcessor):
    """
    Audio processor that generates a sine wave.

    This class implements the AudioProcessor interface to provide a simple sine wave as audio data.

    Attributes:
        frequency (float): The frequency of the sine wave in Hz.
    """

    def __init__(self, total_time: float, sample_rate: int, frequency: float = 1.0):
        """
        Initialize the SinAudioProcessor.

        Args:
            total_time (float): The total duration of the audio in seconds.
            sample_rate (int): The number of samples per second.
            frequency (float, optional): The frequency of the sine wave in Hz. Defaults to 1.0.
        """
        self.frequency = frequency
        super().__init__(total_time, sample_rate)

    def _generate_data(self) -> np.ndarray:
        """
        Generate a sine wave.

        Returns:
            np.ndarray: The generated sine wave data.
        """
        return np.sin(2 * np.pi * self.frequency * self.time)

class WavAudioProcessor(AudioProcessor):
    """
    Audio processor that loads and processes audio files using soundfile.

    This class implements the AudioProcessor interface to work with various audio file formats.

    Attributes:
        filename (str): The path to the audio file.
    """

    def __init__(self, filename: str):
        """
        Initialize the WavAudioProcessor.

        Args:
            filename (str): The path to the audio file.
        """
        self.filename = filename
        with sf.SoundFile(filename) as sound_file:
            self.sample_rate = sound_file.samplerate
            self.total_time = len(sound_file) / self.sample_rate
        super().__init__(self.total_time, self.sample_rate)

    def _generate_data(self) -> np.ndarray:
        """
        Load the audio file data.

        Returns:
            np.ndarray: The loaded audio data.
        """
        audio_data, _ = sf.read(self.filename, always_2d=True)
        # Convert to mono if stereo
        if audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)
        else:
            audio_data = audio_data.flatten()
        return audio_data

    def get_tempo(self, num_bars: int, beats_per_bar: int = 4) -> float:
        """
        Calculate the tempo of the audio file based on its duration and assumed number of bars.

        This method assumes that the entire audio file represents a whole number of bars,
        each with a fixed number of beats.

        Args:
            num_bars (int): The number of bars in the audio file.
            beats_per_bar (int): The number of beats per bar. Defaults to 4 (4/4 time signature).

        Returns:
            float: The calculated tempo in BPM (beats per minute).
        """
        total_beats = num_bars * beats_per_bar
        total_time_minutes = self.total_time / 60
        tempo = total_beats / total_time_minutes
        return tempo
