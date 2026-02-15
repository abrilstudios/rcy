#!/usr/bin/env python3
"""Visualize audio waveform with automatic trim point suggestion.

Creates a PNG showing the full waveform and a zoomed view with the
suggested trim point marked. Useful for visually inspecting drum samples
before trimming.

Usage:
    audio-viz <file.wav>                    # Create visualization at /tmp/audio_viz.png
    audio-viz <file.wav> <output.png>       # Save to specific path
    audio-viz <file.wav> --max-duration 0.3 # Change max duration
"""

import sys
import argparse
import numpy as np
import librosa
import matplotlib.pyplot as plt


def analyze_trim_point(y, sr, max_duration=0.5, threshold_db=-40):
    """Find suggested trim point based on amplitude envelope."""
    peak = np.max(np.abs(y))
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    rms_db = librosa.amplitude_to_db(rms, ref=peak)
    
    below_threshold = np.where(rms_db < threshold_db)[0]
    if len(below_threshold) > 0:
        for i in range(len(below_threshold) - 2):
            if (below_threshold[i+1] == below_threshold[i] + 1 and 
                below_threshold[i+2] == below_threshold[i] + 2):
                suggested_trim = rms_times[below_threshold[i]]
                break
        else:
            suggested_trim = min(max_duration, len(y)/sr)
    else:
        suggested_trim = min(max_duration, len(y)/sr)
    
    return min(suggested_trim + 0.05, len(y)/sr)


def visualize(input_path, output_path, max_duration=0.5):
    """Create waveform visualization with trim suggestion."""
    # Load audio
    y, sr = librosa.load(input_path, sr=None, mono=True)
    duration = len(y) / sr
    trim_point = analyze_trim_point(y, sr, max_duration)
    
    # Create plot
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
    ax1.set_title(f'{input_path} - Full Waveform ({duration:.2f}s)')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Zoomed view
    zoom_time = min(trim_point + 0.2, duration)
    zoom_samples = int(zoom_time * sr)
    ax2.plot(time[:zoom_samples], y[:zoom_samples], linewidth=0.8, color='steelblue')
    ax2.axvline(trim_point, color='red', linestyle='--', linewidth=2,
                label=f'Trim at {trim_point:.3f}s')
    ax2.fill_betweenx(ax2.get_ylim(), 0, trim_point,
                       color='green', alpha=0.1, label='Keep (useful audio)')
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Amplitude')
    ax2.set_title('Zoomed View - Useful Audio Region')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    
    print(f'Visualization saved to {output_path}')
    print(f'Duration: {duration:.2f}s -> suggested trim: {trim_point:.2f}s ({(1-trim_point/duration)*100:.1f}% reduction)')
    
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Visualize audio waveform with trim point suggestion'
    )
    parser.add_argument('input', help='Input WAV file')
    parser.add_argument('output', nargs='?', default='/tmp/audio_viz.png',
                        help='Output PNG path (default: /tmp/audio_viz.png)')
    parser.add_argument('--max-duration', '-m', type=float, default=0.5,
                        help='Maximum duration for trim suggestion (default: 0.5s)')
    parser.add_argument('--open', '-o', action='store_true',
                        help='Open visualization after creating')
    
    args = parser.parse_args()
    
    viz_path = visualize(args.input, args.output, args.max_duration)
    
    if args.open:
        import subprocess
        subprocess.run(['open', viz_path], check=False)


if __name__ == '__main__':
    main()
