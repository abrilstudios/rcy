#!/usr/bin/env python
"""
Test script to check BPM calculation with different measure values.
This will load the given file and test different measure values to see how BPM changes.
"""
import os
from audio_processor import WavAudioProcessor

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
    # Get the project root directory
    import pathlib
    current_file = pathlib.Path(__file__)
    project_root = current_file.parent.parent.parent
    
    files = [
        os.path.join(project_root, "presets/amen_classic/amen.wav"),
        os.path.join(project_root, "tutorials/sordid/wav/one_track_mind_extract.wav"),
    ]
    
    # Test with different measure values
    measure_values = [1, 2, 3, 4, 8, 16]
    
    for file_path in files:
        if os.path.exists(file_path):
            test_bpm_calculation(file_path, measure_values)
        else:
            print(f"File not found: {file_path}")