"""
Test different segment creation methods with MIDI export.

This test file verifies that MIDI exports are correct regardless of how segments are created:
1. By measures (split_by_measures)
2. By transients (split_by_transients)
3. By user-added markers/segments (add_segment)
4. By start/end markers only

Additionally, it tests segment boundary consistency to ensure:
- Implicit boundaries (start and end of file) are correctly included
- Zero-length segments are properly skipped
- MIDI notes consistently match the exported WAV segments
"""
import os
import tempfile
import pathlib
import numpy as np
from unittest.mock import patch, MagicMock
import pytest

# Import modules using conftest.py setup for PYTHONPATH
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
        
        # Check boundary creation - split_by_measures returns boundaries (segments + 1)
        assert len(segments) == (num_measures * resolution) + 1
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export segments
            export_stats = ExportUtils.export_segments(audio_processor, tempo, num_measures, temp_dir)
            
            # Check the exported MIDI file using the path from export_stats
            midi_path = export_stats['midi_path']
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
            
        # For transients, check actual segment count based on mocked data
        # From debug output: we get 5 segments total, which means 6 boundaries
        assert len(segments) >= 5, f"Expected at least 5 boundaries, got {len(segments)}"
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export segments
            export_stats = ExportUtils.export_segments(audio_processor, tempo, num_measures, temp_dir)
            
            # Check the exported MIDI file
            midi_path = export_stats['midi_path']
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
            # Check that WAV files match the actual segments created
            actual_segments = len(audio_processor.segment_manager.get_all_segments())
            assert len(wav_files) == actual_segments, f"Expected {actual_segments} WAV files, got {len(wav_files)}"
    
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
        
        # Add 7 internal boundaries to create 8 segments (including start/end boundaries)
        for i in range(1, 8):
            segment_pos = int(total_samples * i / 8)
            audio_processor.add_segment(segment_pos / audio_processor.sample_rate)
        
        # Check segment creation - should have 8 segments with start/end boundaries
        segments = audio_processor.segment_manager.get_all_segments()
        assert len(segments) == 8
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export segments
            export_stats = ExportUtils.export_segments(audio_processor, tempo, num_measures, temp_dir)
            
            # Check the exported MIDI file
            midi_path = export_stats['midi_path']
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
        
        # Start with initial state (single segment covering entire file)
        # No need to clear - new SegmentManager handles this correctly
        
        # Define start and end markers at 25% and 75% of the file
        start_marker_pos = audio_processor.total_time * 0.25
        end_marker_pos = audio_processor.total_time * 0.75
        
        # Create a temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export using markers but no segments
            export_stats = ExportUtils.export_segments(audio_processor, tempo, num_measures, temp_dir, 
                                        start_marker_pos, end_marker_pos)
            
            # Check the exported MIDI file
            midi_path = export_stats['midi_path'] 
            assert os.path.exists(midi_path), "MIDI file was not created"
            
            # Analyze the MIDI file
            result = analyze_midi(midi_path)
            
            # Verify the time signature
            assert result['time_signature'] == (4, 4), \
                f"Time signature should be 4/4, got {result['time_signature']}"
            
            # Verify WAV files were exported
            # With start/end markers but no segments, we should get 1 WAV file
            # (the selection from start marker to end marker)
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            assert len(wav_files) == 1, f"Expected 1 WAV file, got {len(wav_files)}"


class TestSegmentBoundaryConsistency:
    """Tests specifically for segment boundary consistency issues"""
    
    class MockAudioProcessor:
        """Simple audio processor mock for testing segment boundary consistency"""
        
        def __init__(self, segments=None, duration=1.0, sample_rate=44100):
            """Initialize with optional segments, duration, and sample rate"""
            from segment_manager import SegmentManager
            
            self.sample_rate = sample_rate
            self.is_stereo = True
            self.playback_tempo_enabled = False
            self.source_bpm = 120.0
            self.target_bpm = 120.0
            
            # Create simple test data
            total_samples = int(duration * sample_rate)
            self.data_left = np.ones(total_samples)
            self.data_right = np.ones(total_samples)
            self.total_time = duration
            
            # Initialize SegmentManager with audio context
            self.segment_manager = SegmentManager()
            self.segment_manager.set_audio_context(total_samples, sample_rate)
            
            # Add internal boundaries if provided
            if segments:
                # Filter out start/end boundaries (new SegmentManager handles these automatically)
                internal_segments = [s for s in segments if s != 0 and s != total_samples]
                if internal_segments:
                    self.segment_manager.split_by_positions(internal_segments)
            
        def get_tempo(self, num_measures):
            """Return a fixed tempo for testing"""
            return 120.0
    
    def test_segment_boundary_inclusion(self):
        """Test that start/end boundaries are included in export even when not in segments"""
        # Create a mock processor with 2 user-added segments at 1/3 and 2/3 of the file
        # This should create 3 total segments when exported
        duration = 3.0  # seconds
        sample_rate = 44100
        total_samples = int(duration * sample_rate)
        
        # Create a model with segments at 1/3 and 2/3 of the file (NO start/end boundaries)
        model = self.MockAudioProcessor(
            segments=[
                total_samples // 3,      # At 1 second
                (total_samples * 2) // 3  # At 2 seconds
            ],
            duration=duration,
            sample_rate=sample_rate
        )
        
        # Verify SegmentManager automatically creates 3 segments with start/end boundaries
        segments = model.segment_manager.get_all_segments()
        assert len(segments) == 3, "Should have 3 segments: [0-1s], [1s-2s], [2s-3s]"
        
        # Export to a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Capture export_stats return value
            export_stats = ExportUtils.export_segments(model, 120.0, 4, temp_dir)
            
            # Check the exported WAV files - should be 3 segments
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            assert len(wav_files) == 3, "Expected 3 segments including implicit boundaries"
            
            # Check MIDI note count
            midi_path = export_stats['midi_path']
            result = analyze_midi(midi_path)
            assert result['note_count'] == 3, "Expected 3 MIDI notes matching segment count"
    
    def test_continuous_midi_timing(self):
        """Test that continuous MIDI timing produces expected results with no gaps"""
        # Use the apache_break preset for a real-world test case
        processor = WavAudioProcessor(preset_id='apache_break')
        
        # Add several segment markers (not evenly spaced to test gap handling)
        total_samples = len(processor.data_left)
        segment_positions = [
            int(total_samples * 0.1),   # 10% into file
            int(total_samples * 0.3),   # 30% into file
            int(total_samples * 0.6),   # 60% into file
            int(total_samples * 0.8),   # 80% into file
        ]
        # Add segment boundaries one by one
        for pos_sample in segment_positions:
            pos_time = pos_sample / processor.sample_rate
            processor.add_segment(pos_time)
        
        # Calculate the source BPM for proper timing
        processor.calculate_source_bpm(measures=2)
        tempo = processor.get_tempo(2)
        
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export with continuous timing (default)
            export_stats = ExportUtils.export_segments(
                processor, tempo, 2, temp_dir
            )
            
            # Verify MIDI note count
            midi_path = export_stats['midi_path']
            result = analyze_midi(midi_path)
            
            # There should be 5 segments (with start/end boundaries)
            assert result['note_count'] == 5, "Expected 5 MIDI notes"
            
            # Check number of WAV files
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            assert len(wav_files) == 5, "Expected 5 WAV files"
            
            # VALIDATE NO GAPS: Use mido to verify there are no gaps in the continuous mode
            # Step 1: Read the MIDI file with mido
            import mido
            mid = mido.MidiFile(midi_path)
            
            # Step 2: Extract all note events
            note_events = []
            for track in mid.tracks:
                cumulative_ticks = 0
                for msg in track:
                    cumulative_ticks += msg.time
                    if msg.type == 'note_on' and msg.velocity > 0:
                        note_events.append({
                            'type': 'on',
                            'note': msg.note,
                            'tick': cumulative_ticks
                        })
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        note_events.append({
                            'type': 'off',
                            'note': msg.note,
                            'tick': cumulative_ticks
                        })
            
            # Step 3: Find note start and end ticks
            notes = []
            active_notes = {}
            
            for event in sorted(note_events, key=lambda x: x['tick']):
                if event['type'] == 'on':
                    active_notes[event['note']] = event['tick']
                elif event['type'] == 'off' and event['note'] in active_notes:
                    notes.append({
                        'note': event['note'],
                        'start': active_notes[event['note']],
                        'end': event['tick']
                    })
                    del active_notes[event['note']]
            
            # Step 4: Sort notes by start time
            notes.sort(key=lambda x: x['start'])
            
            # Step 5: Verify there are no gaps between consecutive notes
            for i in range(1, len(notes)):
                # The start of the current note should be exactly at the end of the previous note
                prev_end = notes[i-1]['end']
                current_start = notes[i]['start']
                
                # Check for a gap (allowing for extremely small floating-point differences)
                gap = current_start - prev_end
                assert abs(gap) <= 1, f"Gap detected between notes {i} and {i+1}: {gap} ticks (tolerance: ±1 tick)"
    
    def test_zero_length_segment_handling(self):
        """Test that zero-length segments are properly skipped in export"""
        # Create a mock processor with a duplicate segment marker
        # This creates a zero-length segment that should be skipped
        duration = 2.0  # seconds
        sample_rate = 44100
        total_samples = int(duration * sample_rate)
        
        # Create segments with a duplicate (zero-length segment) - NO start/end boundaries
        model = self.MockAudioProcessor(
            segments=[
                total_samples // 4,         # At 0.5 seconds
                total_samples // 4,         # Same position - creates zero-length segment
                total_samples // 2,         # At 1 second
                (total_samples * 3) // 4    # At 1.5 seconds
            ],
            duration=duration,
            sample_rate=sample_rate
        )
        
        # Verify initial segments - duplicates should be removed by SegmentManager
        segments = model.segment_manager.get_all_segments()
        assert len(segments) == 4, "Should have 4 segments with start/end boundaries"
        
        # Export to a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Capture export_stats return value
            export_stats = ExportUtils.export_segments(model, 120.0, 4, temp_dir)
            
            # Should have 4 segments
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            assert len(wav_files) == 4, "Expected 4 segments"
            
            # Check MIDI note count
            midi_path = export_stats['midi_path']
            result = analyze_midi(midi_path)
            assert result['note_count'] == 4, "Expected 4 MIDI notes matching segment count"
            
            # Check SFZ file consistency
            sfz_path = export_stats['sfz_path']
            with open(sfz_path, 'r') as f:
                sfz_content = f.read()
                assert sfz_content.count("<region>") == 4, "Expected 4 regions in SFZ file"
    
    def test_missing_start_boundary(self):
        """Test that file start boundary is added when missing"""
        # Create a mock processor with segments that don't include the start
        duration = 2.0  # seconds
        sample_rate = 44100
        total_samples = int(duration * sample_rate)
        
        # Create segments starting at 0.5s
        model = self.MockAudioProcessor(
            segments=[
                total_samples // 4,         # At 0.5 seconds
                total_samples // 2,         # At 1 second
                (total_samples * 3) // 4    # At 1.5 seconds
            ],
            duration=duration,
            sample_rate=sample_rate
        )
        
        # Export to a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Capture export_stats return value
            export_stats = ExportUtils.export_segments(model, 120.0, 4, temp_dir)
            
            # We should have 4 segments
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            
            # Verify WAV file count
            assert len(wav_files) == 4, "Expected 4 WAV segments"
            
            # Check MIDI note count
            midi_path = export_stats['midi_path']
            result = analyze_midi(midi_path)
            assert result['note_count'] == 4, "Expected 4 MIDI notes matching segment count"
    
    def test_missing_end_boundary(self):
        """Test that file end boundary is added when missing"""
        # Create a mock processor with segments that don't include the end
        duration = 2.0  # seconds
        sample_rate = 44100
        total_samples = int(duration * sample_rate)
        
        # Create segments up to 1.5s
        model = self.MockAudioProcessor(
            segments=[
                total_samples // 4,         # At 0.5 seconds
                total_samples // 2,         # At 1 second
                (total_samples * 3) // 4    # At 1.5 seconds
            ],
            duration=duration,
            sample_rate=sample_rate
        )
        
        # Export to a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Capture export_stats return value
            export_stats = ExportUtils.export_segments(model, 120.0, 4, temp_dir)
            
            # We should have 4 segments
            wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
            
            # Verify WAV file count
            assert len(wav_files) == 4, "Expected 4 WAV segments"
            
            # Check MIDI note count
            midi_path = export_stats['midi_path']
            result = analyze_midi(midi_path)
            assert result['note_count'] == 4, "Expected 4 MIDI notes matching segment count"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])