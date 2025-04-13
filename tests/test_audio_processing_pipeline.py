import pytest
import numpy as np
import sys
import os
import pathlib

# Add source directory to Python path
current_file = pathlib.Path(__file__)
src_dir = current_file.parent.parent / "src" / "python"
sys.path.append(str(src_dir))

from audio_processor import (
    extract_segment,
    apply_playback_tempo,
    apply_tail_fade,
    reverse_segment,
    process_segment_for_output
)

# Test extraction function
def test_extract_segment_mono():
    # Create test data (1 second of 440Hz sine wave at 44.1kHz)
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    data_left = np.sin(2 * np.pi * 440 * t)
    data_right = data_left.copy()
    
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

def test_extract_segment_stereo():
    # Create test data (1 second of 440Hz sine wave at 44.1kHz)
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    data_left = np.sin(2 * np.pi * 440 * t)
    data_right = np.sin(2 * np.pi * 880 * t)  # Right channel = 880Hz
    
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

def test_extract_segment_invalid_range():
    # Create test data
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

# Test playback tempo function
def test_apply_playback_tempo():
    # Create a simple segment
    segment = np.ones((1000,))  # Mono segment
    original_sample_rate = 44100
    
    # Test with playback tempo disabled
    seg_out, rate_out = apply_playback_tempo(
        segment, original_sample_rate, 100, 160, enabled=False
    )
    assert rate_out == original_sample_rate  # Should be unchanged
    
    # Test with invalid BPM values
    seg_out, rate_out = apply_playback_tempo(
        segment, original_sample_rate, None, 160, enabled=True
    )
    assert rate_out == original_sample_rate  # Should be unchanged
    
    # Test with valid values
    source_bpm = 100
    target_bpm = 160
    seg_out, rate_out = apply_playback_tempo(
        segment, original_sample_rate, source_bpm, target_bpm, enabled=True
    )
    
    # Check sample rate adjusted correctly (160/100 = 1.6x)
    expected_rate = int(original_sample_rate * (target_bpm / source_bpm))
    assert rate_out == expected_rate
    assert rate_out == int(44100 * 1.6)

# Test tail fade function
def test_apply_tail_fade_disabled():
    # Create test data
    segment = np.ones((1000,))  # All ones
    
    # Should return unchanged when disabled
    result = apply_tail_fade(segment, 44100, is_stereo=False, enabled=False)
    np.testing.assert_array_equal(result, segment)

def test_apply_tail_fade_mono():
    # Create test data (all ones)
    sample_rate = 44100
    fade_duration_ms = 50
    # Calculate expected fade length in samples
    fade_samples = int((fade_duration_ms / 1000) * sample_rate)
    # Make the segment exactly 3x the fade length
    segment = np.ones((fade_samples * 3,))
    
    # Apply 50ms linear fade
    result = apply_tail_fade(
        segment, sample_rate, is_stereo=False, enabled=True,
        duration_ms=fade_duration_ms, curve="linear"
    )
    
    # Check shape
    assert result.shape == segment.shape
    
    # Check start of array unchanged (first 2/3 of array)
    np.testing.assert_array_equal(result[:-fade_samples], segment[:-fade_samples])
    
    # Check fade applied correctly - should decrease linearly to 0
    fade_part = result[-fade_samples:]
    assert fade_part[0] == 1.0  # Start of fade should be 1.0
    assert fade_part[-1] == 0.0  # End of fade should be 0.0
    assert fade_part[fade_samples//2] == pytest.approx(0.5, abs=0.01)  # Middle should be ~0.5

def test_apply_tail_fade_stereo():
    # Create test data (stereo, all ones)
    sample_rate = 44100
    fade_duration_ms = 50
    # Calculate expected fade length in samples
    fade_samples = int((fade_duration_ms / 1000) * sample_rate)
    # Make the segment exactly 3x the fade length
    segment = np.ones((fade_samples * 3, 2))
    
    # Apply 50ms exponential fade
    result = apply_tail_fade(
        segment, sample_rate, is_stereo=True, enabled=True,
        duration_ms=fade_duration_ms, curve="exponential"
    )
    
    # Check fade applied to both channels
    left_fade = result[-fade_samples:, 0]
    right_fade = result[-fade_samples:, 1]
    
    # Both channels should have identical fade
    np.testing.assert_array_equal(left_fade, right_fade)
    
    # Check fade values
    assert left_fade[0] == 1.0  # Start of fade should be 1.0
    assert left_fade[-1] == 0.0  # End of fade should be 0.0
    
    # Check fade curve shape: 
    # - First quarter should have small change (slow start to fade)
    # - Last quarter should have larger change (quick drop at end)
    quarter_idx = fade_samples // 4
    first_quarter_change = 1.0 - left_fade[quarter_idx]
    last_quarter_change = left_fade[-quarter_idx] - 0.0
    
    # Exponential fade should have larger change at the end
    assert last_quarter_change > first_quarter_change

# Test reverse function
def test_reverse_segment_mono():
    # Create test data (linear ramp)
    segment = np.arange(100)
    
    # Reverse
    result = reverse_segment(segment, is_stereo=False)
    
    # Check it's reversed
    np.testing.assert_array_equal(result, segment[::-1])
    
    # Check original not modified
    assert segment[0] == 0
    assert segment[-1] == 99

def test_reverse_segment_stereo():
    # Create test data (stereo with different channels)
    left = np.arange(100)
    right = np.arange(100, 200)
    segment = np.column_stack((left, right))
    
    # Reverse
    result = reverse_segment(segment, is_stereo=True)
    
    # Check each channel is reversed
    np.testing.assert_array_equal(result[:, 0], left[::-1])
    np.testing.assert_array_equal(result[:, 1], right[::-1])

# Test full pipeline
def test_process_segment_for_output():
    # Create test data
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    data_left = np.sin(2 * np.pi * 440 * t)
    data_right = np.sin(2 * np.pi * 440 * t)
    
    # Process segment with different settings
    start_sample = int(0.25 * sample_rate)
    end_sample = int(0.75 * sample_rate)
    
    # Test 1: No effects (plain extraction)
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
    
    # Test 2: With tempo adjustment
    segment, out_rate = process_segment_for_output(
        data_left, data_right, start_sample, end_sample,
        sample_rate=sample_rate,
        is_stereo=False,
        reverse=False,
        playback_tempo_enabled=True,
        source_bpm=100,
        target_bpm=120,
        tail_fade_enabled=False
    )
    
    # Sample rate should be adjusted to match tempo ratio
    assert out_rate == int(sample_rate * (120/100))
    
    # Test 3: With reverse
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
    
    # Test 4: With tail fade
    segment, out_rate = process_segment_for_output(
        data_left, data_right, start_sample, end_sample,
        sample_rate=sample_rate,
        is_stereo=False,
        reverse=False,
        playback_tempo_enabled=False,
        tail_fade_enabled=True,
        fade_duration_ms=100,
        fade_curve="linear"
    )
    
    # Fade duration in samples
    fade_samples = int((100 / 1000) * sample_rate)
    
    # Check end of array fades to 0
    assert segment[-1] == 0.0
    
    # Test 5: All effects together
    segment, out_rate = process_segment_for_output(
        data_left, data_right, start_sample, end_sample,
        sample_rate=sample_rate,
        is_stereo=True,
        reverse=True,
        playback_tempo_enabled=True,
        source_bpm=100,
        target_bpm=120,
        tail_fade_enabled=True,
        fade_duration_ms=100,
        fade_curve="exponential"
    )
    
    # Check basics
    assert segment.shape == (end_sample - start_sample, 2)  # Should be stereo
    assert segment[-1, 0] == 0.0  # Should fade to 0 (left)
    assert segment[-1, 1] == 0.0  # Should fade to 0 (right)
    assert out_rate == int(sample_rate * (120/100))  # Rate should be adjusted