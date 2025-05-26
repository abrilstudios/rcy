"""
Tests for MIDI time signature export functionality in RCY.

This module tests:
- MIDI time signature encoding with different denominator values
- Custom MIDIFileWithMetadata class time signature handling
- ExportUtils MIDI file generation with correct time signatures
"""
import pytest
import tempfile
import os
import numpy as np
from midiutil import MIDIFile

# Import modules using conftest.py setup for PYTHONPATH
from utils.midi_analyzer import analyze_midi
from export_utils import MIDIFileWithMetadata


class TestMIDITimeSignature:
    """Tests for MIDI time signature encoding and handling."""
    
    def test_time_signature_encoding(self):
        """Test that MIDI time signatures are correctly encoded with various denominators."""
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

    def test_custom_midi_file_time_signature(self):
        """Test MIDIFileWithMetadata handles time signatures correctly."""
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
            
        finally:
            # Clean up the test file
            if os.path.exists(midi_path):
                os.remove(midi_path)

    def test_export_utils_integration(self, sample_audio_data):
        """Test ExportUtils creates MIDI files with correct time signatures."""
        # Import ExportUtils
        from export_utils import ExportUtils
        
        # Create a simple model-like object with the required attributes
        class MockSegmentManager:
            def __init__(self, audio_duration, sample_rate):
                self.total_duration = audio_duration
                # Create 4 equal segments
                segment_duration = audio_duration / 4
                self.segments = []
                for i in range(4):
                    start_time = i * segment_duration
                    end_time = (i + 1) * segment_duration
                    self.segments.append((start_time, end_time))
            
            def get_all_segments(self):
                return self.segments
        
        class MockModel:
            def __init__(self, audio_data):
                self.data_left = audio_data['data_left']
                self.data_right = audio_data['data_right']
                self.is_stereo = True
                self.sample_rate = audio_data['sample_rate']
                self.playback_tempo_enabled = False
                self.source_bpm = 120
                self.target_bpm = 120
                # Create mock segment manager
                audio_duration = len(self.data_left) / self.sample_rate
                self.segment_manager = MockSegmentManager(audio_duration, self.sample_rate)
                
            def get_tempo(self, num_measures):
                return 120.0
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as export_dir:
            # Export segments
            mock_model = MockModel(sample_audio_data)
            ExportUtils.export_segments(mock_model, 120.0, 4, export_dir)
            
            # The MIDI filename will be based on the directory name
            dir_name = os.path.basename(os.path.normpath(export_dir))
            midi_filename = f"{dir_name}.mid"
            exported_midi_path = os.path.join(export_dir, midi_filename)
            assert os.path.exists(exported_midi_path), f"Exported MIDI file ({midi_filename}) not found"
            
            # Analyze the exported MIDI file
            export_result = analyze_midi(exported_midi_path)
            
            # Verify the time signature in the exported file
            assert export_result['time_signature'] is not None, "No time signature found in exported MIDI"
            export_time_sig = f"{export_result['time_signature'][0]}/{export_result['time_signature'][1]}"
            assert export_time_sig == "4/4", f"Expected 4/4 but got {export_time_sig} in exported MIDI"
            
            # Verify other properties
            assert export_result['tempo'] == 120.0, f"Expected tempo 120.0 BPM but got {export_result['tempo']} in exported MIDI"