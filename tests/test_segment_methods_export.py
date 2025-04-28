"""
Test different segment creation methods with MIDI export.

This test file verifies that MIDI exports are correct regardless of how segments are created:
1. By measures (split_by_measures)
2. By transients (split_by_transients)
3. By user-added markers/segments (add_segment)
"""
import os
import tempfile
import sys
import pathlib
import numpy as np
from unittest.mock import patch, MagicMock
import pytest

# Add source directory to Python path
current_file = pathlib.Path(__file__)
src_dir = current_file.parent.parent / "src" / "python"
sys.path.append(str(src_dir))

from audio_processor import WavAudioProcessor
from export_utils import ExportUtils
from utils.midi_analyzer import analyze_midi


class TestSegmentMethodsExport:
    """Tests for different segment creation methods and export."""
    
    @pytest.fixture
    def audio_processor(self):
        """Create a WavAudioProcessor instance with apache_break preset."""
        processor = WavAudioProcessor(preset_id='apache_break')
        return processor
    
    def test_split_by_measures_and_export(self, audio_processor):
        """Test split_by_measures creates correct segments and MIDI export."""
        # Set number of measures and resolution
        num_measures = 2
        resolution = 4
        
        # Calculate source BPM
        audio_processor.calculate_source_bpm(measures=num_measures)
        
        # Get the tempo
        tempo = audio_processor.get_tempo(num_measures)
        
        # Split by measures
        segments = audio_processor.split_by_measures(num_measures, resolution)
        
        # Check segment creation
        assert len(segments) == (num_measures * resolution) + 1
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export segments
            ExportUtils.export_segments(audio_processor, tempo, num_measures, temp_dir)
            
            # Check the exported MIDI file
            midi_path = os.path.join(temp_dir, "sequence.mid")
            assert os.path.exists(midi_path), "MIDI file was not created"
            
            # Analyze the MIDI file
            result = analyze_midi(midi_path)
            
            # Verify the time signature, beats, and bars
            assert result['time_signature'] == (4, 4), f"Time signature should be 4/4, got {result['time_signature']}"
            beats_expectation = num_measures * 4  # 4 beats per measure
            assert abs(result['total_beats'] - beats_expectation) < 0.1, \
                f"Expected {beats_expectation} beats, got {result['total_beats']}"
            assert abs(result['total_bars'] - num_measures) < 0.1, \
                f"Expected {num_measures} bars, got {result['total_bars']}"
            
            # Verify correct number of WAV files were exported
            expected_wav_count = num_measures * resolution
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            assert len(wav_files) == expected_wav_count, \
                f"Expected {expected_wav_count} WAV files, got {len(wav_files)}"
    
    def test_split_by_transients_and_export(self, audio_processor):
        """Test split_by_transients creates correct segments and MIDI export."""
        # Set number of measures
        num_measures = 2
        
        # Calculate source BPM
        audio_processor.calculate_source_bpm(measures=num_measures)
        
        # Get the tempo
        tempo = audio_processor.get_tempo(num_measures)
        
        # Mock librosa's onset detection for predictable results
        with patch('librosa.onset.onset_strength', return_value=np.array([0.1, 0.2, 0.3])), \
             patch('librosa.onset.onset_detect', return_value=np.array([1, 2, 3, 4, 5])), \
             patch('librosa.frames_to_samples', return_value=np.array([
                 # Create 8 evenly spaced segments (9 points) for consistency with split_by_measures
                 int(len(audio_processor.data_left) * i / 8) for i in range(1, 9)
             ])):
                
            # Split by transients
            segments = audio_processor.split_by_transients(threshold=0.3)
            
            # For transients, we get segments returned as the points inside the file
        # not including start (0) and end, so verify that
        assert len(segments) == 8
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export segments
            ExportUtils.export_segments(audio_processor, tempo, num_measures, temp_dir)
            
            # Check the exported MIDI file
            midi_path = os.path.join(temp_dir, "sequence.mid")
            assert os.path.exists(midi_path), "MIDI file was not created"
            
            # Analyze the MIDI file
            result = analyze_midi(midi_path)
            
            # Verify the time signature, beats, and bars
            assert result['time_signature'] == (4, 4), \
                f"Time signature should be 4/4, got {result['time_signature']}"
            
            # Beats and bars might differ from split_by_measures since transients
            # don't necessarily align with measures, but time signature should be correct.
            
            # Verify WAV files were exported
            # When split_by_transients is used, first segment (0 to first marker) 
            # is added by ExportUtils if it doesn't exist
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            assert len(wav_files) > 0, "No WAV files were exported"
            assert len(wav_files) == 8, f"Expected 8 WAV files, got {len(wav_files)}"
    
    def test_user_added_segments_and_export(self, audio_processor):
        """Test user-added segments and MIDI export."""
        # Set number of measures
        num_measures = 2
        
        # Calculate source BPM
        audio_processor.calculate_source_bpm(measures=num_measures)
        
        # Get the tempo
        tempo = audio_processor.get_tempo(num_measures)
        
        # Total audio length in samples
        total_samples = len(audio_processor.data_left)
        
        # Manually add 8 evenly-spaced segments
        audio_processor.segments = []
        for i in range(1, 9):
            segment_pos = int(total_samples * i / 8)
            audio_processor.add_segment(segment_pos / audio_processor.sample_rate)
        
        # Sort segments (should already be sorted but just to be sure)
        audio_processor.segments.sort()
        
        # Check segment creation
        assert len(audio_processor.segments) == 8
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export segments
            ExportUtils.export_segments(audio_processor, tempo, num_measures, temp_dir)
            
            # Check the exported MIDI file
            midi_path = os.path.join(temp_dir, "sequence.mid")
            assert os.path.exists(midi_path), "MIDI file was not created"
            
            # Analyze the MIDI file
            result = analyze_midi(midi_path)
            
            # Verify the time signature
            assert result['time_signature'] == (4, 4), \
                f"Time signature should be 4/4, got {result['time_signature']}"
            
            # Verify WAV files were exported
            # The segments created should actually result in 8 WAV files because:
            # 1. We manually created 8 evenly-spaced segments
            # 2. ExportUtils processes the segments as pairs
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            
            # We should get 8 WAV files (not 9, because the 8th marker is at the end of the file)
            assert len(wav_files) == 8, \
                f"Expected 8 WAV files, got {len(wav_files)}"
    
    def test_start_end_markers_and_export(self, audio_processor):
        """Test start/end markers with no segments and MIDI export."""
        # Set number of measures
        num_measures = 2
        
        # Calculate source BPM
        audio_processor.calculate_source_bpm(measures=num_measures)
        
        # Get the tempo
        tempo = audio_processor.get_tempo(num_measures)
        
        # Clear any existing segments
        audio_processor.segments = []
        
        # Define start and end markers at 25% and 75% of the file
        start_marker_pos = audio_processor.total_time * 0.25
        end_marker_pos = audio_processor.total_time * 0.75
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export using markers but no segments
            ExportUtils.export_segments(audio_processor, tempo, num_measures, temp_dir, 
                                        start_marker_pos, end_marker_pos)
            
            # Check the exported MIDI file
            midi_path = os.path.join(temp_dir, "sequence.mid")
            assert os.path.exists(midi_path), "MIDI file was not created"
            
            # Analyze the MIDI file
            result = analyze_midi(midi_path)
            
            # Verify the time signature
            assert result['time_signature'] == (4, 4), \
                f"Time signature should be 4/4, got {result['time_signature']}"
            
            # Verify WAV files were exported
            # Actually, start/end markers create 3 segments:
            # 1. From beginning to start marker
            # 2. From start marker to end marker (the selection itself)
            # 3. From end marker to end of file
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            assert len(wav_files) == 3, f"Expected 3 WAV files, got {len(wav_files)}"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])