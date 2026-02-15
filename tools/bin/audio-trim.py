#!/usr/bin/env python3
"""Analyze audio files and suggest optimal trim points for drum samples.

Usage:
    audio-trim <file.wav>                    # Analyze and suggest trim point
    audio-trim <file.wav> --visualize        # Show waveform with trim point
    audio-trim <file.wav> --trim <output>    # Actually trim the file
    audio-trim <file.wav> --max-duration 0.5 # Set max duration (default 0.5s)

The tool analyzes the amplitude envelope to find where the drum hit ends
and the reverb tail begins, suggesting an optimal trim point.
"""

import sys
import argparse
import numpy as np
import librosa
import soundfile as sf


def analyze_trim_point(y, sr, max_duration=0.5, threshold_db=-40):
    """Analyze audio and suggest optimal trim point.
    
    Args:
        y: Audio samples
        sr: Sample rate
        max_duration: Maximum duration in seconds
        threshold_db: dB threshold below peak for tail detection
    
    Returns:
        dict with analysis results
    """
    duration = len(y) / sr
    
    # Find peak and calculate RMS envelope
    peak = np.max(np.abs(y))
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    
    # Convert to dB
    rms_db = librosa.amplitude_to_db(rms, ref=peak)
    
    # Find where signal drops below threshold
    below_threshold = np.where(rms_db < threshold_db)[0]
    if len(below_threshold) > 0:
        # Find first sustained drop (3 consecutive frames below threshold)
        for i in range(len(below_threshold) - 2):
            if (below_threshold[i+1] == below_threshold[i] + 1 and 
                below_threshold[i+2] == below_threshold[i] + 2):
                suggested_trim = rms_times[below_threshold[i]]
                break
        else:
            suggested_trim = min(max_duration, duration)
    else:
        suggested_trim = min(max_duration, duration)
    
    # Constrain to max_duration
    suggested_trim = min(suggested_trim, max_duration)
    
    # Add small fade margin
    fade_margin = 0.05  # 50ms
    suggested_trim = min(suggested_trim + fade_margin, duration)
    
    return {
        'original_duration': duration,
        'original_samples': len(y),
        'suggested_trim_time': suggested_trim,
        'suggested_trim_samples': int(suggested_trim * sr),
        'reduction_percent': (1 - suggested_trim/duration) * 100,
        'peak_amplitude': peak,
        'sample_rate': sr,
    }


def visualize_trim(y, sr, trim_point, output_path='/tmp/audio_trim_analysis.png'):
    """Create visualization showing waveform and suggested trim point."""
    import matplotlib.pyplot as plt
    
    duration = len(y) / sr
    time = np.linspace(0, duration, len(y))
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))
    
    # Full waveform
    ax1.plot(time, y, linewidth=0.5, color='steelblue')
    ax1.axvline(trim_point, color='red', linestyle='--', linewidth=2, 
                label=f'Suggested trim: {trim_point:.3f}s')
    ax1.fill_betweenx(ax1.get_ylim(), trim_point, duration, 
                       color='red', alpha=0.1, label='Remove (tail)')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Amplitude')
    ax1.set_title('Full Waveform Analysis')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Zoomed to suggested duration + 0.2s context
    zoom_time = min(trim_point + 0.2, duration)
    zoom_samples = int(zoom_time * sr)
    ax2.plot(time[:zoom_samples], y[:zoom_samples], linewidth=0.8, color='steelblue')
    ax2.axvline(trim_point, color='red', linestyle='--', linewidth=2,
                label=f'Trim at {trim_point:.3f}s')
    ax2.fill_betweenx(ax2.get_ylim(), 0, trim_point, 
                       color='green', alpha=0.1, label='Keep (drum hit)')
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Amplitude')
    ax2.set_title('Zoomed View - Useful Audio')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f'Visualization saved to {output_path}')
    return output_path


def trim_audio(y, sr, trim_samples, output_path):
    """Trim audio and save to output file."""
    y_trimmed = y[:trim_samples]
    sf.write(output_path, y_trimmed, sr)
    print(f'Trimmed audio saved to {output_path}')
    print(f'  Original: {len(y)} samples ({len(y)/sr:.2f}s)')
    print(f'  Trimmed:  {len(y_trimmed)} samples ({len(y_trimmed)/sr:.2f}s)')


def main():
    parser = argparse.ArgumentParser(
        description='Analyze audio files and suggest optimal trim points for drum samples'
    )
    parser.add_argument('input', help='Input WAV file')
    parser.add_argument('--visualize', '-v', action='store_true',
                        help='Create visualization PNG')
    parser.add_argument('--trim', '-t', metavar='OUTPUT',
                        help='Trim audio and save to OUTPUT file')
    parser.add_argument('--max-duration', '-m', type=float, default=0.5,
                        help='Maximum duration in seconds (default: 0.5)')
    parser.add_argument('--threshold', type=float, default=-40,
                        help='Threshold in dB below peak for tail detection (default: -40)')
    parser.add_argument('--output-viz', default='/tmp/audio_trim_analysis.png',
                        help='Path for visualization PNG (default: /tmp/audio_trim_analysis.png)')
    
    args = parser.parse_args()
    
    # Load audio
    print(f'Loading {args.input}...')
    y, sr = librosa.load(args.input, sr=None, mono=True)
    
    # Analyze
    result = analyze_trim_point(y, sr, args.max_duration, args.threshold)
    
    print(f'\nAnalysis Results:')
    print(f'  Original duration:   {result["original_duration"]:.3f}s ({result["original_samples"]} samples)')
    print(f'  Suggested trim:      {result["suggested_trim_time"]:.3f}s ({result["suggested_trim_samples"]} samples)')
    print(f'  Reduction:           {result["reduction_percent"]:.1f}%')
    print(f'  Peak amplitude:      {result["peak_amplitude"]:.4f}')
    print(f'  Sample rate:         {result["sample_rate"]} Hz')
    
    # Visualize if requested
    if args.visualize:
        print()
        viz_path = visualize_trim(y, sr, result['suggested_trim_time'], args.output_viz)
        import subprocess
        subprocess.run(['open', viz_path], check=False)
    
    # Trim if requested
    if args.trim:
        print()
        trim_audio(y, sr, result['suggested_trim_samples'], args.trim)


if __name__ == '__main__':
    main()
