#!/usr/bin/env python
"""
Test script to check BPM calculation with different measure values.
This will load the given file and test different measure values to see how BPM changes.
"""
import os
import sys

# Add src directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'src')
sys.path.insert(0, src_dir)

from python.audio_processor import WavAudioProcessor

def test_bpm_calculation(file_path, measure_values):
    """Test BPM calculation with different measure values."""
    print(f"\n===== BPM CALCULATION TEST FOR: {file_path} =====")
    print(f"File: {os.path.basename(file_path)}")
    
    # Create audio processor
    processor = WavAudioProcessor()
    
    # Load file directly
    processor.set_filename(file_path)
    
    # Print basic file info
    print(f"Duration: {processor.total_time:.6f}s")
    
    # Test each measure value
    print("\nMeasure | BPM")
    print("--------|--------")
    for measures in measure_values:
        bpm = processor.calculate_source_bpm(measures=measures)
        print(f"{measures:7} | {bpm:.2f}")
    
    print("=====================================\n")

if __name__ == "__main__":
    # Files to test
    files = [
        "presets/amen_classic/amen.wav",
        "tutorials/sordid/wav/one_track_mind_extract.wav",
    ]
    
    # Test with different measure values
    measure_values = [1, 2, 4, 8, 16]
    
    for file_path in files:
        abs_path = os.path.join(script_dir, file_path)
        if os.path.exists(abs_path):
            test_bpm_calculation(abs_path, measure_values)
        else:
            print(f"File not found: {abs_path}")