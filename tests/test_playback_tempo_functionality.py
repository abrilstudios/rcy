"""
Tests for the playback tempo adjustment feature functionality.
Run with: PYTHONPATH=./src/python pytest tests/test_playback_tempo_functionality.py -v
"""

import pytest
from audio_processor import WavAudioProcessor
import numpy as np

class TestPlaybackTempo:
    """Test suite for playback tempo adjustment feature."""
    
    @pytest.fixture(params=['amen_classic', 'apache_break'])
    def processor(self, request):
        """Fixture to create a WavAudioProcessor with the specified preset."""
        return WavAudioProcessor(preset_id=request.param)
    
    def test_preset_loading_and_measures(self, processor):
        """Test that presets load correctly with the right measures."""
        preset_id = processor.preset_id
        preset_info = processor.preset_info
        
        assert preset_info is not None, f"Failed to load preset info for {preset_id}"
        assert 'measures' in preset_info, f"Missing 'measures' in preset info for {preset_id}"
        
        expected_measures = {
            'amen_classic': 4,
            'apache_break': 2
        }
        
        assert preset_info['measures'] == expected_measures[preset_id], \
            f"Expected {expected_measures[preset_id]} measures for {preset_id}, got {preset_info.get('measures')}"
    
    def test_source_bpm_calculation(self, processor):
        """Test that source BPM is calculated correctly from measures and duration."""
        preset_id = processor.preset_id
        measures = processor.preset_info.get('measures', 4)
        duration = processor.total_time
        beats = measures * 4  # Assuming 4/4 time
        
        expected_bpm = (60.0 * beats) / duration
        actual_bpm = processor.source_bpm
        
        assert abs(actual_bpm - expected_bpm) < 0.1, \
            f"For {preset_id}: expected BPM {expected_bpm:.2f}, got {actual_bpm:.2f}"
        
        # Expected approximate values for each preset
        expected_approx = {
            'amen_classic': 138.0,  # ~137.72 actual
            'apache_break': 120.0   # ~120.00 actual
        }
        
        assert abs(actual_bpm - expected_approx[preset_id]) < 1.0, \
            f"BPM for {preset_id} ({actual_bpm:.2f}) differs from expected ({expected_approx[preset_id]:.2f})"
    
    def test_playback_ratio_calculation(self, processor):
        """Test that playback ratio is correctly calculated based on source and target BPM."""
        preset_id = processor.preset_id
        source_bpm = processor.source_bpm
        
        processor.playback_tempo_enabled = True
        
        # Test cases with different target BPMs
        test_bpms = [100, 120, 140, 160, 180]
        
        for target_bpm in test_bpms:
            processor.target_bpm = target_bpm
            expected_ratio = target_bpm / source_bpm
            actual_ratio = processor.get_playback_ratio()
            
            assert abs(actual_ratio - expected_ratio) < 0.01, \
                f"For {preset_id} with target={target_bpm}, expected ratio {expected_ratio:.4f}, got {actual_ratio:.4f}"
    
    def test_sample_rate_adjustment(self, processor):
        """Test that sample rate is correctly adjusted based on playback ratio."""
        preset_id = processor.preset_id
        original_rate = processor.sample_rate
        source_bpm = processor.source_bpm
        
        processor.playback_tempo_enabled = True
        
        # Test with different target BPMs
        for target_bpm in [120, 140, 160]:
            processor.target_bpm = target_bpm
            ratio = processor.get_playback_ratio()
            expected_rate = int(original_rate * ratio)
            actual_rate = processor.get_adjusted_sample_rate()
            
            assert actual_rate == expected_rate, \
                f"For {preset_id} with target={target_bpm}, expected rate {expected_rate}Hz, got {actual_rate}Hz"
    
    def test_ratio_extremes(self, processor):
        """Test ratio calculation at extreme BPM targets."""
        preset_id = processor.preset_id
        processor.playback_tempo_enabled = True
        
        # Test with very slow tempo
        processor.target_bpm = 60
        slow_ratio = processor.get_playback_ratio()
        
        # Test with very fast tempo
        processor.target_bpm = 240
        fast_ratio = processor.get_playback_ratio()
        
        # 240 BPM should be faster than all our preset tempos
        assert fast_ratio > 1.0, \
            f"For {preset_id} with target=240, ratio {fast_ratio:.2f} should be > 1.0"
            
        # The ratio relationship should be proportional
        assert abs((fast_ratio / slow_ratio) - 4.0) < 0.1, \
            f"For {preset_id}, ratio at 240 BPM should be ~4x ratio at 60 BPM, but got {fast_ratio:.2f}/{slow_ratio:.2f}={fast_ratio/slow_ratio:.2f}"

    def test_disabled_playback_tempo(self, processor):
        """Test that disabled playback tempo returns unmodified sample rate."""
        original_rate = processor.sample_rate
        
        # Disabled by default
        assert processor.playback_tempo_enabled == False
        
        # Should return original rate when disabled
        assert processor.get_adjusted_sample_rate() == original_rate
        
        # Ratio should be 1.0 when disabled
        assert processor.get_playback_ratio() == 1.0

    @pytest.mark.parametrize("reverse", [False, True])
    def test_segment_playback_integration(self, processor, reverse):
        """Test that playback segment function correctly uses the adjusted sample rate."""
        processor.playback_tempo_enabled = True
        processor.target_bpm = 160
        
        # Create a test segment (start is important, end is less important)
        start_time = 0.0
        end_time = min(1.0, processor.total_time)
        
        # Mock method to prevent actual audio playback
        original_play = processor.play_segment
        
        try:
            # Track calls to capture parameters
            calls = []
            
            def mock_play_segment(start, end, reverse=False):
                # Just record the call parameters for verification
                calls.append({
                    'start': start,
                    'end': end,
                    'reverse': reverse,
                    'sample_rate': processor.get_adjusted_sample_rate() if processor.playback_tempo_enabled else processor.sample_rate
                })
                return True
            
            processor.play_segment = mock_play_segment
            
            # Call play_segment
            result = processor.play_segment(start_time, end_time, reverse=reverse)
            
            # Verify it was called with correct params
            assert len(calls) == 1
            assert calls[0]['start'] == start_time
            assert calls[0]['end'] == end_time
            assert calls[0]['reverse'] == reverse
            
            # Check that sample rate is adjusted
            expected_rate = int(processor.sample_rate * (160 / processor.source_bpm))
            assert calls[0]['sample_rate'] == expected_rate
            
        finally:
            # Restore original method
            processor.play_segment = original_play