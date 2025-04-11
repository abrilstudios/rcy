"""
audio_preview.py - Utilities for audio waveform downsampling and visualization
"""
import numpy as np
from typing import Tuple, Optional, Union, List


def downsample_waveform(y: np.ndarray, target_length: int = 2000) -> np.ndarray:
    """
    Downsample an audio waveform to a target length using simple striding.
    
    Parameters:
        y (np.ndarray): The input audio waveform array
        target_length (int): The desired output length (default: 2000 samples)
        
    Returns:
        np.ndarray: The downsampled waveform
    """
    if len(y) <= target_length:
        return y  # No downsampling needed
        
    # Calculate stride for simple downsampling
    step = max(1, len(y) // target_length)
    
    # Use slicing with step to downsample
    result = y[::step]
    
    # Ensure result is not longer than target_length
    if len(result) > target_length:
        return result[:target_length]
    
    return result


def downsample_waveform_max_min(y: np.ndarray, target_length: int = 2000) -> np.ndarray:
    """
    Downsample an audio waveform to a target length using max/min envelope.
    This preserves peaks better than simple striding.
    
    Parameters:
        y (np.ndarray): The input audio waveform array
        target_length (int): The desired output length (default: 2000 samples)
        
    Returns:
        np.ndarray: The downsampled waveform with both max and min values
    """
    if len(y) <= target_length:
        return y  # No downsampling needed
    
    # Ensure target_length is even (we'll generate max/min pairs)
    if target_length % 2 != 0:
        target_length -= 1
    
    # Calculate how many samples to group together
    samples_per_bin = len(y) // (target_length // 2)
    
    # Initialize output array (interleaved max/min values)
    downsampled = np.zeros(target_length)
    
    # Generate max/min pairs
    for i in range(target_length // 2):
        start_idx = i * samples_per_bin
        end_idx = min(start_idx + samples_per_bin, len(y))
        
        if start_idx >= len(y) or start_idx >= end_idx:
            break
            
        # Get the bin's data
        bin_data = y[start_idx:end_idx]
        
        # Add a max and min value (interleaved)
        downsampled[i*2] = np.max(bin_data)
        downsampled[i*2+1] = np.min(bin_data)
    
    return downsampled


def get_downsampled_data(
    time: np.ndarray, 
    data_left: np.ndarray, 
    data_right: Optional[np.ndarray] = None,
    target_length: int = 2000,
    method: str = 'max_min'
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """
    Get downsampled time and audio data for efficient visualization.
    
    Parameters:
        time (np.ndarray): Time array
        data_left (np.ndarray): Left channel audio data
        data_right (np.ndarray, optional): Right channel audio data
        target_length (int): Target length for downsampling
        method (str): Downsampling method ('simple' or 'max_min')
        
    Returns:
        tuple: (downsampled_time, downsampled_left, downsampled_right)
    """
    # Choose downsampling function based on method
    if method == 'simple':
        downsample_func = downsample_waveform
    else:  # default to max_min
        downsample_func = downsample_waveform_max_min
        
    # Downsample time array (always use simple striding for time)
    ds_time = downsample_waveform(time, target_length)
    
    # Downsample audio data
    ds_left = downsample_func(data_left, target_length)
    
    # Handle stereo if needed
    ds_right = None
    if data_right is not None:
        ds_right = downsample_func(data_right, target_length)
    
    return ds_time, ds_left, ds_right