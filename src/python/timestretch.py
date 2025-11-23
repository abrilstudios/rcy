from abc import ABC, abstractmethod
from typing import Any
import numpy as np
import librosa
import pyrubberband as pyrb

# Constants to specify the algorithm
PHASE_VOCODER = 'phase_vocoder'
RUBBERBAND = 'rubberband'
LIBROSA_TIME_STRETCH = 'librosa_time_stretch'
STRETCH_WITH_GRAINS = 'stretch_with_grains'


class StretchAlgorithm(ABC):
    """
    Abstract base class for stretch algorithms.
    """

    def __init__(self, audio: np.ndarray, sample_rate: int) -> None:
        self.audio = audio
        self.sample_rate = sample_rate

    @abstractmethod
    def stretch(self, target_length: int, **kwargs: Any) -> np.ndarray:
        """
        Abstract method that must be implemented by subclasses.
        """
        pass


class PhaseVocoderStretch(StretchAlgorithm):
    """
    Phase Vocoder implementation of time-stretching.
    """

    def stretch(self, target_length: int, **kwargs: Any) -> np.ndarray:
        # Calculate the stretch ratio
        original_length = len(self.audio)
        stretch_ratio = target_length / original_length

        # Convert audio to STFT domain
        stft = librosa.stft(y=self.audio)

        # Apply phase vocoder
        stft_stretch = librosa.phase_vocoder(D=stft, rate=stretch_ratio)

        # Convert back to time domain
        return librosa.istft(stft_stretch)


class RubberbandStretch(StretchAlgorithm):
    """
    Rubberband implementation of time-stretching.
    """

    def stretch(self, target_length: int, **kwargs: Any) -> np.ndarray:
        # Calculate the stretch ratio
        original_length = len(self.audio)
        stretch_ratio = target_length / original_length

        # Apply Rubberband time-stretching
        return pyrb.time_stretch(self.audio, self.sample_rate, stretch_ratio)


class LibrosaTimeStretch(StretchAlgorithm):
    """
    Librosa's time_stretch implementation of time-stretching.
    """

    def stretch(self, target_length: int, **kwargs: Any) -> np.ndarray:
        # Calculate the stretch ratio
        original_length = len(self.audio)
        stretch_ratio = target_length / original_length

        # Apply Librosa time-stretch with named arguments
        return librosa.effects.time_stretch(y=self.audio, rate=stretch_ratio)


class StretchWithGrains(StretchAlgorithm):
    """
    Stretching with grains implementation of time-stretching.
    This method breaks the audio into grains (small chunks) and stretches each grain.
    """

    def stretch(self, target_length: int, **kwargs: Any) -> np.ndarray:
        grain_size_ms = kwargs.get('grain_size_ms', 50)  # Default grain size is 50ms

        # Calculate the stretch ratio
        original_length = len(self.audio)
        stretch_ratio = target_length / original_length

        # Calculate grain size in samples
        grain_size = int((grain_size_ms / 1000.0) * self.sample_rate)

        # Break the audio into grains
        grains = [self.audio[i:i + grain_size] for i in range(0, original_length, grain_size)]

        # Time-stretch each grain individually using named arguments
        stretched_grains = [librosa.effects.time_stretch(y=grain, rate=stretch_ratio) for grain in grains]

        # Concatenate the grains back together
        return np.concatenate(stretched_grains)[:target_length]


class TimeStretchManager:
    """
    Manager class to handle different time-stretching algorithms.
    """

    def __init__(self, audio: np.ndarray, sample_rate: int, algorithm: str = PHASE_VOCODER) -> None:
        self.audio = audio
        self.sample_rate = sample_rate
        self.algorithm = algorithm

    def stretch(self, target_length: int, **kwargs: Any) -> np.ndarray:
        """
        Select and apply the appropriate stretch algorithm based on the specified constant.
        Passes algorithm-specific parameters via kwargs.
        """
        if self.algorithm == PHASE_VOCODER:
            stretch_instance = PhaseVocoderStretch(self.audio, self.sample_rate)
        elif self.algorithm == RUBBERBAND:
            stretch_instance = RubberbandStretch(self.audio, self.sample_rate)
        elif self.algorithm == LIBROSA_TIME_STRETCH:
            stretch_instance = LibrosaTimeStretch(self.audio, self.sample_rate)
        elif self.algorithm == STRETCH_WITH_GRAINS:
            stretch_instance = StretchWithGrains(self.audio, self.sample_rate)
        else:
            raise ValueError(f"Unknown stretching algorithm: {self.algorithm}")

        # Call the stretch method of the selected algorithm, passing kwargs if needed
        return stretch_instance.stretch(target_length, **kwargs)


# Example usage:
if __name__ == '__main__':
    # Load an example audio file
    audio, sr = librosa.load('input.wav', sr=44100)

    # Define the target length in samples
    target_length = int(len(audio) * 1.5)  # Stretch by 50%

    # Create a manager instance using stretch_with_grains
    manager = TimeStretchManager(audio, sr, algorithm=STRETCH_WITH_GRAINS)

    # Perform the stretching, passing grain size as a parameter
    stretched_audio = manager.stretch(target_length, grain_size_ms=10)

    # Save the stretched audio to a file
    librosa.output.write_wav('output.wav', stretched_audio, sr)

