"""
Audio Processing Utilities

This module contains shared audio processing functions that can be used
by both the traditional and high-performance audio engines.
"""

import numpy as np
import librosa
from config_manager import config


def extract_segment(data_left, data_right, start_sample, end_sample, is_stereo=False):
    """Extract a slice of audio from source data
    
    Args:
        data_left: Left channel audio data
        data_right: Right channel audio data (same as left for mono)
        start_sample: Start sample index
        end_sample: End sample index
        is_stereo: Whether to create a stereo segment
        
    Returns:
        np.ndarray: Audio segment (mono or stereo)
    """
    # Validate sample range
    if start_sample < 0 or start_sample >= len(data_left) or end_sample > len(data_left):
        raise ValueError(f"Invalid sample range: {start_sample} to {end_sample}, data length: {len(data_left)}")
    
    # Ensure start < end
    if start_sample >= end_sample:
        raise ValueError(f"Start sample must be less than end sample: {start_sample} >= {end_sample}")
    
    # Extract segment based on stereo/mono
    if is_stereo:
        left_segment = data_left[start_sample:end_sample]
        right_segment = data_right[start_sample:end_sample]
        segment = np.column_stack((left_segment, right_segment))
    else:
        segment = data_left[start_sample:end_sample]
    
    return segment


def apply_playback_tempo(segment, original_sample_rate, source_bpm, target_bpm, enabled=True):
    """Apply tempo adjustment via sample rate modification
    
    Args:
        segment: Audio segment data (mono or stereo)
        original_sample_rate: Original sample rate of the audio
        source_bpm: Source BPM of the audio
        target_bpm: Target BPM for playback
        enabled: Whether tempo adjustment is enabled
        
    Returns:
        tuple: (segment, adjusted_sample_rate)
    """
    # Return original if not enabled or invalid BPM values
    if not enabled or target_bpm is None or source_bpm is None or source_bpm <= 0:
        return segment, original_sample_rate
    
    # Calculate the tempo ratio
    tempo_ratio = target_bpm / source_bpm
    
    # Calculate the adjusted sample rate
    adjusted_sample_rate = int(original_sample_rate * tempo_ratio)
    
    return segment, adjusted_sample_rate


def resample_to_standard_rate(segment, adjusted_sample_rate, target_sample_rate=44100, is_stereo=False):
    """Resample audio from adjusted sample rate back to standard rate
    
    This function resamples audio that has been pitch-shifted via sample rate adjustment
    back to a standard sample rate (default 44100 Hz), making it compatible with 
    samplers and DAWs while preserving the pitch shift.
    
    Args:
        segment: Audio segment data (mono or stereo)
        adjusted_sample_rate: Current sample rate of the audio (after tempo adjustment)
        target_sample_rate: Standard sample rate to resample to (default 44100 Hz)
        is_stereo: Whether the segment is stereo (2 channels)
        
    Returns:
        np.ndarray: Resampled audio segment at target_sample_rate
    """
    # No need to resample if rates are nearly identical
    if abs(adjusted_sample_rate - target_sample_rate) < 1.0:
        return segment
    
    # Handle stereo audio (resample each channel separately)
    if is_stereo:
        # Get left and right channels
        left_channel = segment[:, 0]
        right_channel = segment[:, 1]
        
        # Resample each channel
        left_resampled = librosa.resample(
            left_channel, 
            orig_sr=adjusted_sample_rate, 
            target_sr=target_sample_rate,
            res_type='kaiser_best'  # Higher quality resampling, less aliasing
        )
        
        right_resampled = librosa.resample(
            right_channel, 
            orig_sr=adjusted_sample_rate, 
            target_sr=target_sample_rate,
            res_type='kaiser_best'
        )
        
        # Recombine channels
        resampled = np.column_stack((left_resampled, right_resampled))
    else:
        # Mono audio resampling
        resampled = librosa.resample(
            segment, 
            orig_sr=adjusted_sample_rate, 
            target_sr=target_sample_rate,
            res_type='kaiser_best'  # Higher quality resampling, less aliasing
        )
    
    return resampled


def apply_tail_fade(segment, sample_rate, is_stereo=False, enabled=False, duration_ms=10, curve="exponential"):
    """Apply fade-out at the end of a segment
    
    Args:
        segment: Audio segment data (mono or stereo)
        sample_rate: Sample rate of the audio
        is_stereo: Whether segment is stereo (2 channels)
        enabled: Whether fade is enabled
        duration_ms: Duration of fade in milliseconds
        curve: Type of fade curve ("linear" or "exponential")
        
    Returns:
        np.ndarray: Audio segment with fade applied
    """
    # Return original if not enabled or invalid duration
    if not enabled or duration_ms <= 0:
        return segment
    
    # Make a copy to avoid modifying the original
    processed = segment.copy()
    
    # Convert ms to samples
    fade_length_samples = int((duration_ms / 1000) * sample_rate)
    
    # Ensure fade length isn't longer than the segment
    if fade_length_samples > processed.shape[0]:
        fade_length_samples = processed.shape[0]
    
    if fade_length_samples > 0:
        # Create fade curve (from 1.0 to 0.0)
        if curve == "exponential":
            # Create a curve that drops off more quickly (exponential)
            # Using a higher power makes the curve more pronounced
            fade_curve_values = np.linspace(0, 1, fade_length_samples) ** 3
            # Invert so it goes from 1 to 0
            fade_curve_values = 1 - fade_curve_values
        else:  # Linear fade
            fade_curve_values = np.linspace(1, 0, fade_length_samples)
        
        # Apply fade to end of segment
        if is_stereo:
            # Apply to both channels
            start_idx = processed.shape[0] - fade_length_samples
            processed[start_idx:, 0] *= fade_curve_values
            processed[start_idx:, 1] *= fade_curve_values
        else:
            # Apply to mono
            start_idx = processed.shape[0] - fade_length_samples
            processed[start_idx:] *= fade_curve_values
    
    return processed


def reverse_segment(segment, is_stereo=False):
    """Reverse an audio segment
    
    Args:
        segment: Audio segment data (mono or stereo)
        is_stereo: Whether segment is stereo (2 channels)
        
    Returns:
        np.ndarray: Reversed audio segment
    """
    # Make a copy to avoid modifying the original
    processed = segment.copy()
    
    if is_stereo:
        # For stereo audio, we need to flip the rows but keep columns intact
        return np.flipud(processed)
    else:
        # For mono audio, just flip the array
        return np.flip(processed)


def process_segment_for_output(
    data_left,
    data_right,
    start_sample,
    end_sample,
    sample_rate=44100,
    is_stereo=False,
    reverse=False,
    playback_tempo_enabled=False,
    source_bpm=None,
    target_bpm=None,
    tail_fade_enabled=False,
    fade_duration_ms=10,
    fade_curve="exponential",
    for_export=False,
    resample_on_export=True
):
    """Process audio segment through the complete pipeline for output
    
    This function orchestrates the full pipeline:
    1. Extract segment from source data
    2. Apply reverse if needed
    3. Apply playback tempo adjustment
    4. Resample to standard rate (if for_export=True and resample_on_export=True)
    5. Apply tail fade if enabled
    
    Args:
        data_left: Left channel audio data
        data_right: Right channel audio data (same as left for mono)
        start_sample: Start sample index 
        end_sample: End sample index
        sample_rate: Sample rate of the audio
        is_stereo: Whether to create a stereo segment
        reverse: Whether to reverse the segment
        playback_tempo_enabled: Whether tempo adjustment is enabled
        source_bpm: Source BPM of the audio
        target_bpm: Target BPM for playback
        tail_fade_enabled: Whether to apply fade-out
        fade_duration_ms: Duration of fade in milliseconds
        fade_curve: Type of fade curve ("linear" or "exponential")
        for_export: Whether this processing is for export (vs. playback)
        resample_on_export: Whether to resample to standard rate on export
        
    Returns:
        tuple: (processed_segment, output_sample_rate)
    """
    # Stage 1: Extract the segment
    segment = extract_segment(
        data_left, data_right, start_sample, end_sample, is_stereo
    )
    
    # Stage 2: Apply reverse if needed
    if reverse:
        segment = reverse_segment(segment, is_stereo)
    
    # Stage 3: Apply playback tempo adjustment
    segment, adjusted_sample_rate = apply_playback_tempo(
        segment, sample_rate, source_bpm, target_bpm, playback_tempo_enabled
    )
    
    # Store the original adjusted rate for return value
    output_sample_rate = adjusted_sample_rate
    
    # Stage 4: Resample to standard sample rate for playback or export
    if playback_tempo_enabled and adjusted_sample_rate != sample_rate:
        if for_export and resample_on_export:
            # For export, resample and use original sample rate in WAV header
            segment = resample_to_standard_rate(
                segment, adjusted_sample_rate, sample_rate, is_stereo
            )
            output_sample_rate = sample_rate
        elif not for_export:
            # For playback, always resample back to standard rate so audio system can play it
            segment = resample_to_standard_rate(
                segment, adjusted_sample_rate, sample_rate, is_stereo
            )
            output_sample_rate = sample_rate
    
    # Stage 5: Apply tail fade
    segment = apply_tail_fade(
        segment, adjusted_sample_rate, is_stereo, tail_fade_enabled, fade_duration_ms, fade_curve
    )
    
    return segment, output_sample_rate