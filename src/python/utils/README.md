# Audio Utils

Utility functions for audio processing and visualization in the RCY application.

## Downsampling Audio Data

The `audio_preview.py` module provides functionality for downsampling audio waveforms for more efficient visualization. This is critical for large audio files where rendering full-resolution waveforms is inefficient and unnecessary.

### Downsampling Methods

Two primary downsampling methods are provided:

1. **Simple Striding** (`downsample_waveform`): Takes evenly spaced samples from the original waveform. Fast and simple, but may miss peaks between sampled points.

2. **Max-Min Envelope** (`downsample_waveform_max_min`): Creates a visual envelope that preserves peaks by storing both maximum and minimum values for each segment. This provides a more accurate visual representation of the audio waveform, especially for high-frequency content.

### Usage

```python
from utils.audio_preview import get_downsampled_data

# For visualization, downsample the data
ds_time, ds_left, ds_right = get_downsampled_data(
    time=time_array,
    data_left=left_channel_data,
    data_right=right_channel_data,  # Optional, for stereo files
    target_length=2000,  # Target number of samples for visualization
    method='max_min'  # 'simple' or 'max_min'
)

# Use the downsampled data for plotting
plt.plot(ds_time, ds_left)
```

### Benefits

- **Performance**: Dramatically reduces the amount of data that needs to be rendered, improving UI responsiveness
- **Memory Efficiency**: Lower memory usage since we're plotting fewer points
- **Visual Accuracy**: The max-min method preserves peaks and valleys, maintaining an accurate visual representation
- **Consistent Visualization**: Provides a consistent level of detail regardless of zoom level

### Integration

These downsampling functions are specifically designed to be used with both Matplotlib and PyQtGraph visualization backends. The same downsampled data can be used with either rendering library.

## Testing

The downsampling algorithms are fully unit tested. Run the tests with:

```bash
pytest tests/utils/test_audio_preview.py -v
```