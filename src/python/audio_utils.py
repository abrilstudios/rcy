"""
Audio Processing Utilities

This module contains shared audio processing functions that can be used
by both the traditional and high-performance audio engines.

Uses simple linear interpolation for tempo adjustment to create the
characteristic sound of vintage hardware samplers (Akai S1000 style).
"""

import numpy as np
from config_manager import config


def extract_segment(
    data_left: np.ndarray,
    data_right: np.ndarray,
    start_sample: int,
    end_sample: int,
    is_stereo: bool = False
) -> np.ndarray:
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


def simple_tempo_resample(
    segment: np.ndarray,
    tempo_ratio: float,
    is_stereo: bool = False
) -> np.ndarray:
    """Simple tempo adjustment via linear interpolation (Akai-style).

    Creates characteristic vintage sampler artifacts by using basic sample
    decimation/interpolation rather than FFT-based reconstruction.

    This matches the behavior of early hardware samplers like the Akai S1000,
    which did not perform bandlimited reconstruction.

    Args:
        segment: Audio segment to resample
        tempo_ratio: target_bpm / source_bpm (e.g., 2.0 for 2x faster)
        is_stereo: Whether the segment is stereo

    Returns:
        Resampled audio segment with adjusted tempo

    Examples:
        120 BPM → 240 BPM (ratio=2.0): Creates half as many samples (decimation)
        120 BPM → 60 BPM (ratio=0.5): Creates twice as many samples (interpolation)
    """
    if abs(tempo_ratio - 1.0) < 0.001:
        # No change needed
        return segment

    if is_stereo:
        # Process stereo channels separately
        old_length = segment.shape[0]
        new_length = int(old_length / tempo_ratio)

        # Create interpolation indices
        old_indices = np.arange(old_length)
        new_indices = np.linspace(0, old_length - 1, new_length)

        # Linear interpolation for each channel
        left_resampled = np.interp(new_indices, old_indices, segment[:, 0])
        right_resampled = np.interp(new_indices, old_indices, segment[:, 1])

        return np.column_stack((left_resampled, right_resampled))
    else:
        # Process mono
        old_length = len(segment)
        new_length = int(old_length / tempo_ratio)

        # Create interpolation indices
        old_indices = np.arange(old_length)
        new_indices = np.linspace(0, old_length - 1, new_length)

        # Linear interpolation
        return np.interp(new_indices, old_indices, segment)


def calculate_tempo_adjusted_sample_rate(
    original_sample_rate: int,
    source_bpm: float | None,
    target_bpm: int | None,
    enabled: bool = True
) -> int:
    """Calculate the fake sample rate needed for tempo adjustment via resampling trick
    
    This function calculates what sample rate to tell the resampler the audio is at,
    so that when it "resamples" back to the original rate, it creates a tempo effect.
    
    Args:
        original_sample_rate: Original sample rate of the audio
        source_bpm: Source BPM of the audio
        target_bpm: Target BPM for playback
        enabled: Whether tempo adjustment is enabled
        
    Returns:
        int: The fake "adjusted" sample rate for the resampling trick
    """
    # Return original if not enabled or invalid BPM values
    if not enabled or target_bpm is None or source_bpm is None or source_bpm <= 0:
        return original_sample_rate
    
    # Calculate the tempo ratio
    tempo_ratio = target_bpm / source_bpm
    
    # Calculate the fake sample rate for the resampling trick
    adjusted_sample_rate = int(original_sample_rate * tempo_ratio)
    
    return adjusted_sample_rate


def resample_to_standard_rate(
    segment: np.ndarray,
    adjusted_sample_rate: int,
    target_sample_rate: int = 44100,
    is_stereo: bool = False
) -> np.ndarray:
    """Resample audio from adjusted sample rate back to standard rate (Akai-style).

    Uses simple linear interpolation rather than FFT-based reconstruction to create
    the characteristic sound of vintage hardware samplers like the Akai S1000.

    This function resamples audio that has been tempo-adjusted via sample rate
    manipulation back to a standard sample rate (default 44100 Hz), making it
    compatible with samplers and DAWs.

    Args:
        segment: Audio segment data (mono or stereo)
        adjusted_sample_rate: Current "fake" sample rate (after tempo adjustment)
        target_sample_rate: Standard sample rate to resample to (default 44100 Hz)
        is_stereo: Whether the segment is stereo (2 channels)

    Returns:
        np.ndarray: Resampled audio segment at target_sample_rate

    Examples:
        Original: 1000 samples at "fake" 88200 Hz (2x tempo)
        Result: 500 samples at real 44100 Hz (plays 2x faster)
    """
    # No need to resample if rates are nearly identical
    if abs(adjusted_sample_rate - target_sample_rate) < 1.0:
        return segment

    # Calculate the tempo ratio from the sample rate ratio
    # This is the inverse of what we did in calculate_tempo_adjusted_sample_rate
    tempo_ratio = adjusted_sample_rate / target_sample_rate

    # Use simple linear interpolation (Akai-style)
    return simple_tempo_resample(segment, tempo_ratio, is_stereo)


def apply_tail_fade(
    segment: np.ndarray,
    sample_rate: int,
    is_stereo: bool = False,
    enabled: bool = False,
    duration_ms: int = 10,
    curve: str = "exponential"
) -> np.ndarray:
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


def reverse_segment(segment: np.ndarray, is_stereo: bool = False) -> np.ndarray:
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
    data_left: np.ndarray,
    data_right: np.ndarray,
    start_sample: int,
    end_sample: int,
    sample_rate: int = 44100,
    is_stereo: bool = False,
    reverse: bool = False,
    playback_tempo_enabled: bool = False,
    source_bpm: float | None = None,
    target_bpm: int | None = None,
    tail_fade_enabled: bool = False,
    fade_duration_ms: int = 10,
    fade_curve: str = "exponential",
    for_export: bool = False,
    resample_on_export: bool = True
) -> tuple[np.ndarray, int]:
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
    
    # Stage 3: Calculate fake sample rate for tempo adjustment
    adjusted_sample_rate = calculate_tempo_adjusted_sample_rate(
        sample_rate, source_bpm, target_bpm, playback_tempo_enabled
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
    #segment = apply_tail_fade(
    #    segment, adjusted_sample_rate, is_stereo, tail_fade_enabled, fade_duration_ms, fade_curve
    #)
    
    return segment, output_sample_rate


def process_segment_for_playback(
    data_left: np.ndarray,
    data_right: np.ndarray,
    start_sample: int,
    end_sample: int,
    sample_rate: int = 44100,
    is_stereo: bool = False,
    playback_tempo_enabled: bool = False,
    source_bpm: float | None = None,
    target_bpm: int | None = None,
    tail_fade_enabled: bool = False,
    fade_duration_ms: int = 10,
    fade_curve: str = "exponential",
    for_export: bool = False,
    resample_on_export: bool = True
) -> np.ndarray:
    """Process audio segment through lightweight pipeline for real-time playback
    
    This function provides a streamlined pipeline for real-time playback:
    1. Extract segment from source data
    2. Calculate fake sample rate for tempo adjustment
    3. Resample to standard rate (if for_export=True and resample_on_export=True)
    4. Apply tail fade if enabled
    
    Args:
        data_left: Left channel audio data
        data_right: Right channel audio data (same as left for mono)
        start_sample: Start sample index 
        end_sample: End sample index
        sample_rate: Sample rate of the audio
        is_stereo: Whether to create a stereo segment
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
    
    # Stage 2: Apply tail fade if needed
    #segment = apply_tail_fade(
    #    segment, sample_rate, is_stereo, tail_fade_enabled, fade_duration_ms, fade_curve
    #)
    
    return segment
