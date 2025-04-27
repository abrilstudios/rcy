"""
Test for proper bar and beat calculation in the Apache preset
"""
import pytest
import os
import tempfile
import sys
import pathlib
import numpy as np

# Add source directory to Python path
current_file = pathlib.Path(__file__)
src_dir = current_file.parent.parent / "src" / "python"
sys.path.append(str(src_dir))

from audio_processor import WavAudioProcessor
from export_utils import ExportUtils
from utils.midi_analyzer import analyze_midi


def test_apache_preset_beats_and_bars():
    """Test that the Apache preset properly exports with 8 beats and 2 bars"""
    # Load the Apache preset
    model = WavAudioProcessor(preset_id='apache_break')
    
    # Set number of measures to 2
    num_measures = 2
    
    # Calculate tempo
    tempo = model.get_tempo(num_measures)
    
    # Calculate source BPM 
    model.calculate_source_bpm(measures=num_measures)
    
    # Verify source BPM is approximately 120
    source_bpm = model.source_bpm
    assert 119 <= source_bpm <= 121, f"Expected source_bpm around 120, got {source_bpm}"
    
    # Split audio by measures (4 slices per measure = 8 total for 2 measures)
    slices = model.split_by_measures(num_measures, 4)
    
    # Calculate expected slice times for 2 measures at 4 splits per measure
    sample_rate = model.sample_rate
    total_samples = len(model.data_left)
    
    # Check that we have 9 slices (8 segments + endpoint)
    assert len(slices) == 9, f"Expected 9 slices but got {len(slices)}"
    
    # Create a temporary directory for the export
    with tempfile.TemporaryDirectory() as temp_dir:
        # Export MIDI and slices
        ExportUtils.export_segments(model, tempo, num_measures, temp_dir)
        
        # Check the exported MIDI file
        midi_path = os.path.join(temp_dir, "sequence.mid")
        assert os.path.exists(midi_path), "MIDI file was not created"
        
        # Analyze the MIDI file
        result = analyze_midi(midi_path)
        
        # Check the MIDI file properties
        assert result['time_signature'] == (4, 4), f"Expected time signature 4/4, got {result['time_signature']}"
        assert result['tempo'] == 120, f"Expected tempo 120, got {result['tempo']}"
        
        # We should have exactly 8.0 beats (2 measures * 4 beats per measure)
        assert 7.9 <= result['total_beats'] <= 8.1, f"Expected ~8.0 beats, got {result['total_beats']}"
        
        # We should have exactly 2.0 bars
        assert 1.9 <= result['total_bars'] <= 2.1, f"Expected ~2.0 bars, got {result['total_bars']}"
        
        # Test that all segments have been exported
        wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
        assert len(wav_files) == 8, f"Expected 8 WAV files, got {len(wav_files)}"