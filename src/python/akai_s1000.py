import numpy as np
import librosa
import soundfile as sf
import argparse
from time_stretching import TimeStretchManager, PHASE_VOCODER, RUBBERBAND, LIBROSA_TIME_STRETCH, STRETCH_WITH_GRAINS
from scipy.signal import butter, lfilter

class TimestretchBuilder:
    def __init__(self, audio, sample_rate):
        self.audio = audio
        self.sample_rate = sample_rate
    
    def stretch_with_grains(self, target_length, grain_size_ms=50):
        # Instantiate StretchWithGrains from the time_stretching module
        grain_stretch = StretchWithGrains(self.audio, self.sample_rate)
        
        # Call the stretch method with grain size
        self.audio = grain_stretch.stretch(target_length, grain_size_ms=grain_size_ms)
        return self
    
    def lowpass_filter(self, cutoff_freq=16000):
        nyquist = 0.5 * self.sample_rate
        normal_cutoff = cutoff_freq / nyquist
        b, a = butter(4, normal_cutoff, btype='low', analog=False)
        self.audio = lfilter(b, a, self.audio)
        return self
    
    def add_aliasing(self, downsample_rate=22050):
        downsampled_audio = librosa.resample(self.audio,
                                             orig_sr = self.sample_rate,
                                             target_sr =  downsample_rate)
        self.audio = librosa.resample(downsampled_audio, orig_sr=downsample_rate, target_sr = self.sample_rate)
        return self

    def add_warble(self, depth=0.005, rate=1.5):
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
        """
        Adds subtle pitch drift over time to simulate pitch imperfections.

        Parameters:
            max_drift (float): The maximum pitch drift factor (default is 0.005).

        Returns:
            self: Allows for method chaining.
        """
        # Create a time vector for drift
        t = np.arange(len(self.audio)) / self.sample_rate
        drift = max_drift * np.sin(2 * np.pi * 0.1 * t)  # Slow pitch drift (0.1 Hz)

        # Process pitch shift in small chunks
        chunk_size = 1024  # Size of audio chunks to process
        drifted_audio = []
    
        # Iterate over the audio in chunks and apply pitch shift with varying drift
        for i in range(0, len(self.audio), chunk_size):
            chunk = self.audio[i:i + chunk_size]
            # Apply pitch shift based on the drift value at the chunk's midpoint
            chunk_drift = drift[i:i + chunk_size].mean()  # Use the average drift for this chunk
            shifted_chunk = librosa.effects.pitch_shift(y=chunk, sr=self.sample_rate, n_steps=chunk_drift)
            drifted_audio.append(shifted_chunk)

        # Concatenate all processed chunks back together
        self.audio = np.concatenate(drifted_audio)
        return self

    def save(self, output_file):
        sf.write(output_file, self.audio, self.sample_rate)


def compute_target_length_for_tempo(original_tempo, new_tempo, original_length):
    """
    Computes the new length in samples when time-stretching to a different tempo.
    Stretch ratio = original_tempo / new_tempo.
    """
    stretch_ratio = original_tempo / new_tempo
    target_length = int(original_length * stretch_ratio)
    return target_length


def main():
    parser = argparse.ArgumentParser(description="Apply Akai S1000-style timestretching to an audio file.")
    
    # Required arguments
    parser.add_argument('input_file', type=str, help='Input audio file')
    parser.add_argument('output_file', type=str, help='Output file to save stretched audio')
    
    # Optional arguments
    parser.add_argument('--bars', type=int, default=1, help='Number of bars in the audio (default: 1 bar)')
    parser.add_argument('--original_tempo', type=float, help='Original tempo of the audio in BPM')
    parser.add_argument('--new_tempo', type=float, help='New tempo to stretch the audio to in BPM')
    parser.add_argument('--sample_rate', type=int, default=44100, help='Sample rate (default: 44100 Hz)')
    parser.add_argument('--grain_size', type=int, default=50, help='Grain size in ms (default: 50ms)')
    parser.add_argument('--cutoff_freq', type=int, default=16000, help='Low-pass filter cutoff frequency in Hz (default: 16000 Hz)')
    parser.add_argument('--aliasing', action='store_true', help='Enable aliasing effect (downsample/upsample)')
    parser.add_argument('--warble', action='store_true', help='Enable warble effect (modulated delay)')
    parser.add_argument('--bit_depth', type=int, default=12, help='Bit depth for quantization (default: 12-bit)')
    parser.add_argument('--loop_glitch', action='store_true', help='Enable loop glitch effect (random zeroing of audio segments)')
    parser.add_argument('--pitch_drift', action='store_true', help='Enable pitch drift effect (subtle pitch modulations over time)')

    args = parser.parse_args()

    # Load the audio
    audio, sr = librosa.load(args.input_file, sr=args.sample_rate)
    original_length = len(audio)

    # Compute original tempo if provided and stretch to a new tempo if given
    if args.original_tempo and args.new_tempo:
        print(f"Original tempo: {args.original_tempo} BPM, New tempo: {args.new_tempo} BPM")
        target_length = compute_target_length_for_tempo(args.original_tempo, args.new_tempo, original_length)
    else:
        # Default to original length if tempo not provided
        target_length = original_length
    
    # Build the transformation process
    builder = TimestretchBuilder(audio, sr)

    # Apply transformations
    builder.stretch_with_grains(target_length, grain_size_ms=args.grain_size)

    if args.cutoff_freq:
        builder.lowpass_filter(cutoff_freq=args.cutoff_freq)

    if args.aliasing:
        builder.add_aliasing()

    if args.warble:
        builder.add_warble()

    if args.bit_depth:
        builder.reduce_bit_depth(bit_depth=args.bit_depth)

    if args.loop_glitch:
        builder.add_loop_glitch()

    if args.pitch_drift:
        builder.add_pitch_drift()

    # Save the processed audio
    builder.save(args.output_file)

    print(f"Stretched and processed audio saved to {args.output_file}")


if __name__ == '__main__':
    main()

