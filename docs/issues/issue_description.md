# Moving start/end markers should not automatically enable tempo adjustment

## Issue Description

Currently, when users move the start or end markers in the waveform view, the system automatically enables the tempo adjustment feature (sets playback_tempo_enabled to True). This forces a change in user settings that may not be wanted.

## Current Behavior

In the _update_tempo_from_markers method in rcy_controller.py, there is this line:
```python
# IMPORTANT FIX: Always enable playback tempo when markers change
self.playback_tempo_enabled = True
```

This means that any time markers are moved, the tempo adjustment checkbox is automatically checked, regardless of the user's previous setting.

## Expected Behavior

Moving markers should:
1. Recalculate and update the tempo display
2. Update the source_bpm and target_bpm values 
3. Keep the current playback_tempo_enabled setting (preserve user choice)

## Implementation Notes

1. Remove the line that forces playback_tempo_enabled to True in the _update_tempo_from_markers method
2. Ensure tempo is still recalculated and displayed correctly
3. Only update target_bpm if playback_tempo_enabled is already True

## Related Issues
- This was introduced as part of the fix for #131

## Severity
Medium - This is a usability issue that changes user settings unexpectedly, but doesn't prevent core functionality
