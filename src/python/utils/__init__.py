# Make the utils directory a proper package
from .audio_preview import (
    downsample_waveform,
    downsample_waveform_max_min,
    get_downsampled_data
)

__all__ = [
    'downsample_waveform',
    'downsample_waveform_max_min',
    'get_downsampled_data'
]