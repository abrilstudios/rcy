# Issue: Mono files are displayed as stereo in waveform view

## Problem
When loading a mono audio file (such as a .wav file with only one channel), RCY is incorrectly displaying it as a stereo file with two identical waveforms. This is confusing for users and inconsistent with the actual file properties.

## Details
1. The file `funky-break-kool-is-back_105bpm_E_minor_RIGHT.wav` is actually a mono file (as confirmed by audio analysis tools showing `channels=1`), but is being displayed with two waveforms in RCY.

2. The issue occurs due to how mono files are handled in two parts of the codebase:

   a. In `audio_processor.py` (lines 387-390), mono files are correctly detected but duplicated internally for consistency:
   ```python
   # Mono file - duplicate the channel for consistency in code
   data_left = audio_data.flatten()
   data_right = data_left.copy()
   ```

   b. In `waveform_view.py`, the display mode is solely determined by the config setting:
   ```python
   self.stereo_display = config.get_setting("audio", "stereoDisplay", True)
   ```

   The config.json has `"stereoDisplay": true` which forces dual-waveform display regardless of actual file content.

## Proposed Solution
1. Modify `WavAudioProcessor` to better expose the actual mono/stereo status of loaded files
2. Update `waveform_view.py` to make display decisions based on both:
   - The actual mono/stereo status of the file
   - The user's stereo display preference from config

This will ensure that:
- Mono files display with a single waveform by default
- Stereo files display with two waveforms when stereoDisplay is enabled
- Users can still force dual-display for mono files if desired via config

## Implementation Notes
1. Add a clear `is_mono` property to `WavAudioProcessor`
2. Modify waveform display initialization to check the actual file type
3. Optional: Add a user setting to "Show mono files as stereo" if we want to retain that flexibility

## Testing Plan
1. Test with mono files to verify single waveform display
2. Test with stereo files to verify dual waveform display
3. Verify that config changes still work as expected for stereo files