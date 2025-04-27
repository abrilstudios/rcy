"""
Test for MIDI time signature export in the RCY application
"""
import pytest
import tempfile
import os
import numpy as np
import sys
import pathlib
from midiutil import MIDIFile

# Add source directory to Python path
current_file = pathlib.Path(__file__)
src_dir = current_file.parent.parent / "src" / "python"
sys.path.append(str(src_dir))

# Import modules from src/python
from utils.midi_analyzer import analyze_midi
from export_utils import MIDIFileWithMetadata


def test_midi_time_signature_encoding():
    """Test that MIDI time signatures are correctly encoded"""
    # Test different denominator values and their expected outputs
    test_cases = [
        # (denominator_value, expected_time_signature)
        (1, "4/2"),  # Half notes (2)
        (2, "4/4"),  # Quarter notes (4)
        (3, "4/8"),  # Eighth notes (8)
        (4, "4/16"),  # Sixteenth notes (16)
    ]
    
    for denominator, expected in test_cases:
        # Create a test MIDI file with the specified denominator value
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as temp_file:
            midi_path = temp_file.name
        
        try:
            # Create a MIDI file
            midi = MIDIFile(1)  # One track
            midi.addTempo(0, 0, 120)
            midi.addTimeSignature(0, 0, 4, denominator, 24, 8)
            
            # Add a simple note
            midi.addNote(0, 0, 60, 0, 4, 100)
            
            # Write the MIDI file
            with open(midi_path, "wb") as midi_file:
                midi.writeFile(midi_file)
            
            # Analyze the MIDI file
            result = analyze_midi(midi_path)
            
            # Check the time signature matches our expectation
            assert result['time_signature'] is not None, f"No time signature found for denominator={denominator}"
            time_sig_str = f"{result['time_signature'][0]}/{result['time_signature'][1]}"
            assert time_sig_str == expected, f"Expected {expected} but got {time_sig_str} for denominator={denominator}"
            
        finally:
            # Clean up the test file
            if os.path.exists(midi_path):
                os.remove(midi_path)


def test_export_utils_time_signature():
    """Test that ExportUtils sets the correct time signature value for 4/4"""
    # Create a test file
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as temp_file:
        midi_path = temp_file.name
    
    try:
        # Create a MIDI file using our custom class
        midi = MIDIFileWithMetadata(1)  # One track
        midi.addTempo(0, 0, 120)
        
        # This should produce a 4/4 time signature - using denominator=2
        midi.addTimeSignature(0, 0, 4, 2, 24, 8)
        
        # Add a simple note
        midi.addNote(0, 0, 60, 0, 4, 100)
        
        # Write the MIDI file
        with open(midi_path, "wb") as midi_file:
            midi.writeFile(midi_file)
        
        # Analyze the MIDI file
        result = analyze_midi(midi_path)
        
        # Check the time signature is 4/4
        assert result['time_signature'] is not None, "No time signature found"
        time_sig_str = f"{result['time_signature'][0]}/{result['time_signature'][1]}"
        assert time_sig_str == "4/4", f"Expected 4/4 but got {time_sig_str}"
        
        # Verify other MIDI properties
        assert result['tempo'] == 120.0, f"Expected tempo 120.0 BPM but got {result['tempo']}"
        assert result['ticks_per_beat'] == 960, f"Expected 960 ticks per beat but got {result['ticks_per_beat']}"
        
        # Import ExportUtils and create a real MIDI export
        from export_utils import ExportUtils
        import numpy as np
        
        # Create a simple model-like object with the required attributes
        class MockModel:
            def __init__(self):
                self.data_left = np.ones(44100)  # 1 second of audio at 44.1kHz
                self.data_right = np.ones(44100)
                self.is_stereo = True
                self.sample_rate = 44100
                self.segments = [0, 11025, 22050, 33075, 44100]  # 4 segments of 0.25s each
                self.playback_tempo_enabled = False
                self.source_bpm = 120
                self.target_bpm = 120
            
            def get_segments(self):
                return self.segments
                
            def get_tempo(self, num_measures):
                return 120.0
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as export_dir:
            # Export segments
            mock_model = MockModel()
            ExportUtils.export_segments(mock_model, 120.0, 4, export_dir)
            
            # Check the exported MIDI file
            exported_midi_path = os.path.join(export_dir, "sequence.mid")
            assert os.path.exists(exported_midi_path), "Exported MIDI file not found"
            
            # Analyze the exported MIDI file
            export_result = analyze_midi(exported_midi_path)
            
            # Verify the time signature in the exported file
            assert export_result['time_signature'] is not None, "No time signature found in exported MIDI"
            export_time_sig = f"{export_result['time_signature'][0]}/{export_result['time_signature'][1]}"
            assert export_time_sig == "4/4", f"Expected 4/4 but got {export_time_sig} in exported MIDI"
            
            # Verify other properties
            assert export_result['tempo'] == 120.0, f"Expected tempo 120.0 BPM but got {export_result['tempo']} in exported MIDI"
            
    finally:
        # Clean up the test file
        if os.path.exists(midi_path):
            os.remove(midi_path)