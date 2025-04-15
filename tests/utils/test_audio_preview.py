"""
Tests for audio_preview module - downsampling functionality
"""
import pytest
import numpy as np
from utils.audio_preview import (
    downsample_waveform,
    downsample_waveform_max_min,
    get_downsampled_data
)


class TestDownsampleWaveform:
    """Tests for downsample_waveform function"""

    def test_no_downsampling_needed(self):
        """Should return the original array if it's smaller than target_length"""
        # Arrange
        y = np.array([1, 2, 3, 4, 5])
        target_length = 10
        
        # Act
        result = downsample_waveform(y, target_length)
        
        # Assert
        assert np.array_equal(result, y)
        assert len(result) == len(y)
    
    def test_downsampling_with_exact_division(self):
        """Should downsample by stride when array divides evenly by target length"""
        # Arrange
        y = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        target_length = 5
        
        # Act
        result = downsample_waveform(y, target_length)
        
        # Assert
        assert len(result) == target_length
        assert np.array_equal(result, np.array([1, 3, 5, 7, 9]))
    
    def test_downsampling_with_inexact_division(self):
        """Should handle cases where array length doesn't divide evenly by target length"""
        # Arrange
        y = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        target_length = 4
        
        # Act
        result = downsample_waveform(y, target_length)
        
        # Assert
        assert len(result) <= target_length
        # Stride should be len(y) // target_length = 11 // 4 = 2
        # Result should be truncated to match target_length
        assert np.array_equal(result, np.array([1, 3, 5, 7]))
    
    def test_with_real_audio_data(self, sample_audio_data):
        """Should properly downsample realistic audio data"""
        # Arrange
        data_left = sample_audio_data['data_left']
        original_length = len(data_left)
        target_length = 1000
        
        # Act
        result = downsample_waveform(data_left, target_length)
        
        # Assert
        assert len(result) <= target_length
        # Implementation will truncate to exactly target_length if necessary
        expected_stride = max(1, original_length // target_length)
        expected_length = min(target_length, len(range(0, original_length, expected_stride)))
        assert len(result) == expected_length


class TestDownsampleWaveformMaxMin:
    """Tests for downsample_waveform_max_min function"""
    
    def test_no_downsampling_needed(self):
        """Should return the original array if it's smaller than target_length"""
        # Arrange
        y = np.array([1, 2, 3, 4, 5])
        target_length = 10
        
        # Act
        result = downsample_waveform_max_min(y, target_length)
        
        # Assert
        assert np.array_equal(result, y)
    
    def test_max_min_downsampling(self):
        """Should produce interleaved max/min values"""
        # Arrange
        y = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        target_length = 4  # Will be an even number
        
        # Act
        result = downsample_waveform_max_min(y, target_length)
        
        # Assert
        assert len(result) == target_length
        # First bin: [1,2,3,4,5] -> max=5, min=1
        # Second bin: [6,7,8,9,10] -> max=10, min=6
        assert result[0] == 5  # max of first bin
        assert result[1] == 1  # min of first bin
        assert result[2] == 10  # max of second bin
        assert result[3] == 6  # min of second bin
    
    def test_odd_target_length_adjusted(self):
        """Should adjust odd target length to even"""
        # Arrange
        y = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        target_length = 5  # Odd, should be adjusted to 4
        
        # Act
        result = downsample_waveform_max_min(y, target_length)
        
        # Assert
        assert len(result) == 4  # Adjusted to even
    
    def test_with_real_audio_data(self, sample_audio_data):
        """Should properly downsample realistic audio data"""
        # Arrange
        data_left = sample_audio_data['data_left']
        target_length = 1000
        # Ensure target_length is even
        if target_length % 2 != 0:
            target_length -= 1
            
        # Act
        result = downsample_waveform_max_min(data_left, target_length)
        
        # Assert
        assert len(result) == target_length
        
        # Check that max values are indeed maximums
        samples_per_bin = len(data_left) // (target_length // 2)
        for i in range(5):  # Check first 5 bins
            bin_start = i * samples_per_bin
            bin_end = min(bin_start + samples_per_bin, len(data_left))
            bin_data = data_left[bin_start:bin_end]
            
            assert result[i*2] == pytest.approx(np.max(bin_data))
            assert result[i*2+1] == pytest.approx(np.min(bin_data))


class TestGetDownsampledData:
    """Tests for get_downsampled_data function"""
    
    def test_simple_method(self, sample_audio_data):
        """Should use simple striding method when specified"""
        # Arrange
        time = sample_audio_data['time']
        data_left = sample_audio_data['data_left']
        target_length = 1000
        
        # Act
        ds_time, ds_left, ds_right = get_downsampled_data(
            time, data_left, None, target_length, method='simple'
        )
        
        # Assert
        # Time should be downsampled with simple striding
        assert len(ds_time) <= target_length
        # Left channel should be downsampled with simple striding
        assert len(ds_left) <= target_length
        # Right channel should be None
        assert ds_right is None
        
        # Compare with direct call to ensure correct method was used
        expected_left = downsample_waveform(data_left, target_length)
        assert np.array_equal(ds_left, expected_left)
    
    def test_max_min_method(self, sample_audio_data):
        """Should use max_min method by default"""
        # Arrange
        time = sample_audio_data['time']
        data_left = sample_audio_data['data_left']
        target_length = 1000
        
        # Act
        ds_time, ds_left, ds_right = get_downsampled_data(
            time, data_left, None, target_length
        )
        
        # Assert
        # Time should be downsampled with simple striding
        assert len(ds_time) <= target_length
        # Left channel should be downsampled with max_min
        assert len(ds_left) <= target_length
        # Right channel should be None
        assert ds_right is None
        
        # Compare with direct call to ensure correct method was used
        expected_left = downsample_waveform_max_min(data_left, target_length)
        assert np.array_equal(ds_left, expected_left)
    
    def test_stereo_data(self, sample_audio_data):
        """Should handle stereo data correctly"""
        # Arrange
        time = sample_audio_data['time']
        data_left = sample_audio_data['data_left']
        data_right = sample_audio_data['data_right']
        target_length = 1000
        
        # Act
        ds_time, ds_left, ds_right = get_downsampled_data(
            time, data_left, data_right, target_length
        )
        
        # Assert
        # Time should be downsampled with simple striding
        assert len(ds_time) <= target_length
        # Left channel should be downsampled
        assert len(ds_left) <= target_length
        # Right channel should be downsampled
        assert ds_right is not None
        assert len(ds_right) <= target_length
        
        # Both channels should have the same length
        assert len(ds_left) == len(ds_right)