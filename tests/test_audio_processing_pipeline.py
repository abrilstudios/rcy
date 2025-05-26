"""
Tests for the audio processing pipeline functions.

This module tests the core audio processing functions:
- extract_segment: Extracts a segment of audio
- calculate_tempo_adjusted_sample_rate: Calculates adjusted sample rate for tempo changes
- reverse_segment: Reverses an audio segment
- process_segment_for_output: Combined pipeline for segment processing
"""
import pytest
import numpy as np
import sys
import os
import pathlib

# Import the audio processing functions
from audio_utils import (
    extract_segment,
    calculate_tempo_adjusted_sample_rate,
    reverse_segment,
    process_segment_for_output
)


class TestExtractSegment:
    """Tests for the extract_segment function."""
    
    def test_extract_segment_mono(self, sample_audio_data):
        """Test extracting a mono segment from stereo data."""
        # Get test data from fixture
        data_left = sample_audio_data['data_left']
        data_right = sample_audio_data['data_left'].copy()  # Same for mono test
        sample_rate = sample_audio_data['sample_rate']
        
        # Extract middle 0.5 seconds
        start_sample = int(0.25 * sample_rate)
        end_sample = int(0.75 * sample_rate)
        
        # Extract as mono
        segment = extract_segment(data_left, data_right, start_sample, end_sample, is_stereo=False)
        
        # Check type and shape
        assert isinstance(segment, np.ndarray)
        assert segment.shape == (end_sample - start_sample,)
        assert segment.ndim == 1  # Mono = 1D array
        
        # Check contents match original
        np.testing.assert_array_equal(segment, data_left[start_sample:end_sample])

    def test_extract_segment_stereo(self, sample_audio_data):
        """Test extracting a stereo segment."""
        # Get test data from fixture
        data_left = sample_audio_data['data_left']
        # Use different data for right channel to test stereo
        data_right = np.sin(2 * np.pi * 880 * sample_audio_data['time'])
        sample_rate = sample_audio_data['sample_rate']
        
        # Extract middle 0.5 seconds
        start_sample = int(0.25 * sample_rate)
        end_sample = int(0.75 * sample_rate)
        
        # Extract as stereo
        segment = extract_segment(data_left, data_right, start_sample, end_sample, is_stereo=True)
        
        # Check type and shape
        assert isinstance(segment, np.ndarray)
        assert segment.shape == (end_sample - start_sample, 2)
        assert segment.ndim == 2  # Stereo = 2D array
        
        # Check contents match original
        np.testing.assert_array_equal(segment[:, 0], data_left[start_sample:end_sample])
        np.testing.assert_array_equal(segment[:, 1], data_right[start_sample:end_sample])

    def test_extract_segment_invalid_range(self):
        """Test error handling for invalid range parameters."""
        # Create simple test data
        data_left = np.ones(1000)
        data_right = np.ones(1000)
        
        # Test start < 0
        with pytest.raises(ValueError):
            extract_segment(data_left, data_right, -10, 500)
        
        # Test end > length
        with pytest.raises(ValueError):
            extract_segment(data_left, data_right, 0, 1001)
        
        # Test start >= end
        with pytest.raises(ValueError):
            extract_segment(data_left, data_right, 500, 500)
        with pytest.raises(ValueError):
            extract_segment(data_left, data_right, 600, 500)


class TestPlaybackTempo:
    """Tests for the apply_playback_tempo function."""
    
    def test_playback_tempo_disabled(self):
        """Test that playback tempo adjustment is bypassed when disabled."""
        # Create a simple segment
        segment = np.ones((1000,))  # Mono segment
        original_sample_rate = 44100
        
        # Test with playback tempo disabled
        rate_out = calculate_tempo_adjusted_sample_rate(
            original_sample_rate, 100, 160, enabled=False
        )
        
        # Should return unchanged when disabled
        assert rate_out == original_sample_rate
    
    def test_playback_tempo_invalid_bpm(self):
        """Test handling of invalid BPM values."""
        segment = np.ones((1000,))
        original_sample_rate = 44100
        
        # Test with None BPM
        rate_out = calculate_tempo_adjusted_sample_rate(
            original_sample_rate, None, 160, enabled=True
        )
        assert rate_out == original_sample_rate  # Should be unchanged
        
        # Test with zero BPM
        rate_out = calculate_tempo_adjusted_sample_rate(
            original_sample_rate, 0, 160, enabled=True
        )
        assert rate_out == original_sample_rate  # Should be unchanged
    
    def test_playback_tempo_adjustment(self):
        """Test correct playback tempo adjustment with valid values."""
        segment = np.ones((1000,))
        original_sample_rate = 44100
        source_bpm = 100
        target_bpm = 160
        
        # Apply tempo adjustment
        rate_out = calculate_tempo_adjusted_sample_rate(
            original_sample_rate, source_bpm, target_bpm, enabled=True
        )
        
        # Check sample rate adjusted correctly (160/100 = 1.6x)
        expected_rate = int(original_sample_rate * (target_bpm / source_bpm))
        assert rate_out == expected_rate
        assert rate_out == int(44100 * 1.6)



class TestReverseSegment:
    """Tests for the reverse_segment function."""
    
    def test_reverse_segment_mono(self):
        """Test reversing a mono segment."""
        # Create test data (linear ramp)
        segment = np.arange(100)
        
        # Reverse
        result = reverse_segment(segment, is_stereo=False)
        
        # Check it's reversed
        np.testing.assert_array_equal(result, segment[::-1])
        
        # Check original not modified
        assert segment[0] == 0
        assert segment[-1] == 99
    
    def test_reverse_segment_stereo(self):
        """Test reversing a stereo segment."""
        # Create test data (stereo with different channels)
        left = np.arange(100)
        right = np.arange(100, 200)
        segment = np.column_stack((left, right))
        
        # Reverse
        result = reverse_segment(segment, is_stereo=True)
        
        # Check each channel is reversed
        np.testing.assert_array_equal(result[:, 0], left[::-1])
        np.testing.assert_array_equal(result[:, 1], right[::-1])


class TestProcessSegmentForOutput:
    """Tests for the full process_segment_for_output pipeline."""
    
    def test_process_segment_basic(self, sample_audio_data):
        """Test basic segment processing with no effects."""
        # Get test data from fixture
        data_left = sample_audio_data['data_left']
        data_right = sample_audio_data['data_right']
        sample_rate = sample_audio_data['sample_rate']
        
        # Extract middle 0.5 seconds
        start_sample = int(0.25 * sample_rate)
        end_sample = int(0.75 * sample_rate)
        
        # Process with no effects
        segment, out_rate = process_segment_for_output(
            data_left, data_right, start_sample, end_sample,
            sample_rate=sample_rate,
            is_stereo=False,
            reverse=False,
            playback_tempo_enabled=False,
            tail_fade_enabled=False
        )
        
        # Should match direct extraction
        expected = extract_segment(data_left, data_right, start_sample, end_sample, is_stereo=False)
        np.testing.assert_array_equal(segment, expected)
        assert out_rate == sample_rate
    
    
    def test_process_segment_with_reverse(self, sample_audio_data):
        """Test segment processing with reverse effect."""
        # Get test data from fixture
        data_left = sample_audio_data['data_left']
        data_right = sample_audio_data['data_right']
        sample_rate = sample_audio_data['sample_rate']
        
        # Extract middle 0.5 seconds
        start_sample = int(0.25 * sample_rate)
        end_sample = int(0.75 * sample_rate)
        
        # Process with reverse
        segment, out_rate = process_segment_for_output(
            data_left, data_right, start_sample, end_sample,
            sample_rate=sample_rate,
            is_stereo=False,
            reverse=True,
            playback_tempo_enabled=False,
            tail_fade_enabled=False
        )
        
        # Should be reversed
        expected = extract_segment(data_left, data_right, start_sample, end_sample, is_stereo=False)
        expected = np.flip(expected)
        np.testing.assert_array_equal(segment, expected)
    
