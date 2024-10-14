import numpy as np
import librosa
import soundfile as sf
from scipy.signal import butter, lfilter


class TimestretchBuilder:
    """
    The TimestretchBuilder class allows the composition of various audio transformations
    in a flexible and arbitrary order using the builder pattern. This class processes the audio
    file by passing a NumPy ndarray around for transformation, simulating the behavior of the Akai S1000.

    Each method in the builder modifies the audio ndarray in-place and returns the builder object (self),
    enabling method chaining for easy combination of transformations. The final transformed audio can be
    saved to a file using the save() method.

    Methods:
        stretch_with_grains(target_length, grain_size_ms=50):
            Applies grain-based time-stretching to the audio, simulating the Akai S1000's "choppy" timestretching artifact.
            - target_length: The desired length of the audio in samples.
            - grain_size_ms: Size of each audio grain in milliseconds (default is 50ms).

        lowpass_filter(cutoff_freq=16000):
            Applies a low-pass filter to the audio to simulate the lo-fi frequency response of older samplers.
            - cutoff_freq: The cutoff frequency for the low-pass filter in Hz (default is 16,000 Hz).

        add_aliasing(downsample_rate=22050):
            Simulates aliasing by downsampling and upsampling the audio, introducing digital noise.
            - downsample_rate: The rate to downsample the audio before upsampling again (default is 22,050 Hz).

        add_warble(depth=0.005, rate=1.5):
            Introduces a warble effect by modulating a delay across the audio, creating slight pitch fluctuations.
            - depth: The intensity of the warble effect (default is 0.005).
            - rate: The frequency of the warble in Hz (default is 1.5 Hz).

        reduce_bit_depth(bit_depth=12):
            Reduces the bit depth of the audio to simulate the gritty, low-fidelity sound of older hardware samplers.
            - bit_depth: The target bit depth (default is 12 bits).

        add_loop_glitch(glitch_intensity=0.02):
            Introduces a simulated glitch by zeroing out a small, random segment of the audio to emulate imperfect loop points.
            - glitch_intensity: The fraction of the audio length that will be affected by the glitch (default is 0.02).

        add_pitch_drift(max_drift=0.005):
            Adds subtle pitch drift over time to simulate the pitch imperfections of older samplers.
            - max_drift: The maximum pitch drift factor (default is 0.005).

        save(output_file):
            Saves the transformed audio to the specified file.
            - output_file: The path to save the final processed audio file.
    """
    def __init__(self, audio, sample_rate):
        self.audio = audio
        self.sample_rate = sample_rate
    
    def stretch_with_grains(self, target_length, grain_size_ms=50):
        # Calculate grain size in samples
        grain_size = int((grain_size_ms / 1000.0) * self.sample_rate)
        original_length = len(self.audio)
        stretch_ratio = target_length / original_length

        # Break the audio into grains
        grains = [self.audio[i:i+grain_size] for i in range(0, original_length, grain_size)]
        
        # Time-stretch each grain individually
        stretched_grains = [librosa.effects.time_stretch(grain, stretch_ratio) for grain in grains]
        
        # Concatenate the grains back together
        self.audio = np.concatenate(stretched_grains)[:target_length]  # Trim to target length if necessary
        return self
    
    def lowpass_filter(self, cutoff_freq=16000):
        nyquist = 0.5 * self.sample_rate
        normal_cutoff = cutoff_freq / nyquist
        b, a = butter(4, normal_cutoff, btype='low', analog=False)
        self.audio = lfilter(b, a, self.audio)
        return self
    
    def add_aliasing(self, downsample_rate=22050):
        # Downsample to a lower sample rate
        downsampled_audio = librosa.resample(self.audio, self.sample_rate, downsample_rate)
        
        # Upsample back to original sample rate
        self.audio = librosa.resample(downsampled_audio, downsample_rate, self.sample_rate)
        return self

    def add_warble(self, depth=0.005, rate=1.5):
        # Create a sine wave to modulate delay time
        t = np.arange(len(self.audio)) / self.sample_rate
        modulation = depth * np.sin(2 * np.pi * rate * t)

        warbled_audio = np.zeros_like(self.audio)
        for i in range(len(self.audio)):
            delay_samples = int(modulation[i] * self.sample_rate)
            if i - delay_samples >= 0:
                warbled_audio[i] = (self.audio[i] + self.audio[i - delay_samples]) / 2.0
            else:
                warbled_audio[i] = self.audio[i]
        
        self.audio = warbled_audio
        return self
    
    def reduce_bit_depth(self, bit_depth=12):
        max_val = 2 ** (bit_depth - 1) - 1
        min_val = -max_val - 1
        audio_scaled = np.round(self.audio * max_val)
        audio_clipped = np.clip(audio_scaled, min_val, max_val)
        self.audio = audio_clipped / max_val
        return self

    def add_loop_glitch(self, glitch_intensity=0.02):
        glitch_size = int(len(self.audio) * glitch_intensity)
        glitch_start = np.random.randint(0, len(self.audio) - glitch_size)
        self.audio[glitch_start:glitch_start+glitch_size] = 0
        return self

    def add_pitch_drift(self, max_drift=0.005):
        t = np.arange(len(self.audio)) / self.sample_rate
        drift = max_drift * np.sin(2 * np.pi * 0.1 * t)  # Slow pitch drift (0.1 Hz)
        self.audio = librosa.effects.pitch_shift(self.audio, self.sample_rate, drift)
        return self

    def save(self, output_file):
        sf.write(output_file, self.audio, self.sample_rate)


def main():
    input_file = "input.wav"
    output_file = "output.wav"
    sample_rate = 44100
    target_length = 100000
    
    # Load the audio and start building the process
    audio, sr = librosa.load(file_path, sr=sample_rate)
    builder = TimestretchBuilder(audio, src)
    
    # Apply transformations in arbitrary order
    builder \
        .stretch_with_grains(target_length, grain_size_ms=50) \
        .lowpass_filter(cutoff_freq=12000) \
        .add_aliasing(downsample_rate=22050) \
        .add_warble(depth=0.005, rate=1.5) \
        .reduce_bit_depth(bit_depth=12) \
        .add_loop_glitch(glitch_intensity=0.02) \
        .add_pitch_drift(max_drift=0.005) \
        .save(output_file)

    print(f"Stretched and processed audio saved to {output_file}")


if __name__ == '__main__':
    main()

