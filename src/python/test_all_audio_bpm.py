#!/usr/bin/env python
"""
Test script to check BPM calculation for all WAV files in the specified directory
"""
import os
import glob
from audio_processor import WavAudioProcessor

def test_bpm_calculation(file_path, measure_values=[1]):
    """Test BPM calculation with different measure values."""
    print(f"\n===== BPM CALCULATION TEST FOR: {os.path.basename(file_path)} =====")
    
    try:
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
        return processor.total_time
    except Exception as e:
        print(f"ERROR processing file: {e}")
        print("=====================================\n")
        return None

if __name__ == "__main__":
    # Get the project root directory
    import pathlib
    current_file = pathlib.Path(__file__)
    project_root = current_file.parent.parent.parent
    
    # Directory to search
    wav_dir = os.path.join(project_root, "tutorials/sordid/wav")
    
    # Find all WAV files
    wav_files = glob.glob(os.path.join(wav_dir, "*.wav"))
    
    if not wav_files:
        print(f"No WAV files found in: {wav_dir}")
        exit(1)
    
    print(f"Found {len(wav_files)} WAV files to analyze")
    
    # Test each file with assumed 1 measure
    measure_values = [1]
    
    # Create a summary table
    file_results = []
    
    for file_path in wav_files:
        duration = test_bpm_calculation(file_path, measure_values)
        if duration:
            file_results.append({
                'file': os.path.basename(file_path),
                'duration': duration,
                'bpm_1_measure': 60 * 4 / duration  # BPM with 1 measure assumption
            })
    
    # Print summary table
    print("\n\n===== SUMMARY OF ALL FILES =====")
    print(f"{'Filename':<40} | {'Duration (s)':<12} | {'BPM (1 measure)':<15}")
    print("-" * 70)
    for result in file_results:
        print(f"{result['file']:<40} | {result['duration']:<12.2f} | {result['bpm_1_measure']:<15.2f}")
    print("=====================================")