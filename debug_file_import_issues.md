# RCY File Import Issues - Debug Notes

## Issue Summary
When importing audio files in RCY, there's an issue where files with certain BPM values (specifically 80 BPM .wav files) are not properly displayed in the waveform view. The waveform doesn't show the full file length, and markers/segments are positioned incorrectly.

## Root Cause Analysis
The issue appears to be related to inconsistent use of the audio file's total duration (total_time) across the application components:

1. The model correctly calculates and stores the total duration
2. When downsampling the waveform data for display, this duration might be shortened
3. The waveform view sometimes uses the downsampled data range instead of the original file duration

This creates inconsistencies in:
- Waveform display range
- Marker positions (especially end marker)
- Segment boundary calculations

**Updated Root Cause Insight**: Further analysis suggests that the fundamental issue might be that we're trying to update part of the state while inheriting other parts from the previous file, leading to inconsistent state across the components.

## Attempted Fixes

### First Solution Approach
We tried passing the model's total_time consistently throughout the component chain:

1. In `waveform_view.py`:
   - Modified `update_plot` to accept a `model_total_time` parameter
   - Enhanced logic to prioritize model_total_time over downsampled data range
   - Added debugging to track when total_time changes

2. In `rcy_controller.py`:
   - Modified `update_view` to always pass model's total_time to the waveform view

3. In `rcy_view.py`:
   - Updated `update_plot` to pass through the model_total_time parameter
   - Added direct setting of waveform_view.total_time in update_slices method

However, despite logs showing correct handling of 12-second 80 BPM files, the waveform display still has issues in practice.

### Second Solution Approach: Clean State Reset
A new approach is to treat file imports the same way as application initialization - with a complete state reset:

1. Make `_handle_load_audio_file` in rcy_dispatcher.py perform a full state reset:
```python
# First reset ALL state to initial values
self.store.reset()  # New method to reset state to defaults

# Then load the file and update the state
self.model.set_filename(filename)
# ...rest of the method continues
```

2. Implement a `reset()` method in RcyStore:
```python
def reset(self):
    """Reset the store to initial state."""
    self._state = {
        'audio': {
            'filename': None,
            'total_time': 0,
            'sample_rate': 44100,
            'channels': 1,
            'is_playing': False,
            'current_segment': (None, None),
            'is_playing_reverse': False
        },
        'playback': {
            'tempo_enabled': False,
            'source_bpm': 120,
            'target_bpm': 120,
            'ratio': 1.0,
            'mode': 'one-shot'
        },
        'view': {
            'markers': {
                'start': 0,
                'end': 0
            },
            'segments': [],
            'visible_time': 10,
            'scroll_position': 0,
            'visible_range': (0, 10),
            'active_segment': (None, None)
        },
        'analysis': {
            'measures': 1,
            'threshold': 0.2,
            'tempo': 120,
            'measure_resolution': 4
        }
    }
    # Notify listeners of the reset
    self._notify_listeners("reset")
```

3. Ensure the waveform view properly handles state resets:
```python
# In RcyController._on_state_change
if path == "reset":
    # Force waveform view to reset internal state too
    self.view.reset_internal_state()

# Add method to RcyView
def reset_internal_state(self):
    """Reset internal view state when store is reset."""
    # Reset any cached values or state not directly from the store
    self.waveform_view.reset()
    
# Add method to PyQtGraphWaveformView
def reset(self):
    """Reset internal state."""
    # Clear cached values
    self.time_data = None
    self.total_time = 0
    # Clear segment highlights
    self.clear_active_segment_highlight()
    # Reset any other internal state
```

4. After resetting state, follow the existing initialization path:
   - Update store with the new file's values
   - Allow the controller to handle state updates via subscriptions
   - Let the view update based on those state changes

This approach provides several advantages:
- Eliminates state inconsistencies by starting fresh
- Reuses existing initialization code path
- Properly follows one-way data flow principles
- Simpler than trying to patch specific parts of state

## Specific Observations

### Standard Files (e.g., amen.wav at 137 BPM)
- Correctly loads with ~6.97 second duration
- Waveform displays properly
- Markers position correctly

### 80 BPM .wav Files
- Should display with 12.0 second duration
- Logs show:
  - Correct 12.0 second total_time from model
  - Markers being updated at 0.0 and 12.0 seconds
  - View range being set to 0.0-12.0 seconds
- But visually, the waveform doesn't reflect the complete 12.0 seconds

### Debug Points

Key debug locations to monitor:
1. `waveform_view.py`:
   - `update_plot` method: Verify model_total_time is correctly used
   - `_clamp_markers_to_data_bounds` method: Check if markers are constrained incorrectly
   - `set_visible_range` method: Validate actual view range applied

2. `rcy_controller.py`:
   - `update_view` method: Check if model_total_time is correctly passed
   - Check downsampling logic and its effect on time range

3. `rcy_dispatcher.py`:
   - `_handle_load_audio_file`: Ensure correct total_time is stored in the model and store

## Next Steps for Debugging

1. Add a visual indicator of the model's total_time and the waveform view's total_time
2. Add detailed state dumps when 80 BPM files are detected
3. Add validation checks comparing model_total_time, view range, and time_data_range
4. Consider temporarily hard-coding fixes for 80 BPM files to validate hypotheses
5. Compare PyQtGraph rendering behavior with different file lengths

## Implementation Plan for Clean State Reset

1. Add a `reset()` method to RcyStore
2. Modify `_handle_load_audio_file` to call store.reset() before loading the new file
3. Add a "reset" handler to the controller's _on_state_change method
4. Add reset methods to view components to clear internal state
5. Test with problematic 80 BPM files

## Test Plan for Clean State Reset Implementation

### Phase 1: Individual Component Testing

1. **RcyStore reset() method**
   - Create a simple test to verify the reset() method correctly resets all state values to defaults
   - Test that store notifications are sent correctly on reset
   - Verify that deep nesting of state objects (e.g., view.markers.start) is reset properly

2. **RcyController reset handling**
   - Create a mock view and verify that controller calls view.reset_internal_state() when store is reset
   - Test that controller's internal state is properly reset
   - Verify that subscriptions are maintained after reset

3. **WaveformView reset method**
   - Create a test to verify waveform_view.reset() properly clears all internal state
   - Test that PyQtGraph components are correctly reset
   - Verify that markers and highlights are cleared

### Phase 2: Integration Testing

4. **File Loading Sequence**
   - Test loading a file after reset, verifying state values at each step
   - Create an integration test that loads a standard file, then loads a problematic 80 BPM file
   - Verify that marker positions, visible range, and total_time are correct after each load

5. **User Interface Components**
   - Verify that UI elements (sliders, inputs, displays) reflect the correct state after reset and file load
   - Test that marker handles appear at the correct positions after file load
   - Verify that zoom and scroll controls work correctly with new file dimensions

### Phase 3: Edge Case Testing

6. **Various File Types**
   - Test with files of different lengths (very short and very long)
   - Test with files of different BPM values (especially 80 BPM files)
   - Test with different audio formats (wav, mp3, etc.)

7. **Rapid State Transitions**
   - Test rapidly loading different files in succession
   - Verify that UI remains consistent and doesn't display artifacts from previous files
   - Test loading a file during playback or marker dragging

### Phase 4: Debugging Helpers

8. **Validation Helpers**
   - Add temporary validation code that compares model_total_time, view_total_time, and visible range
   - Create status display showing current file length and view bounds
   - Implement state consistency checks that run after each file load

### Manual Testing Checklist

- [ ] Load amen.wav and verify correct display (6.97s)
- [ ] Load an 80 BPM file and verify correct display (12.0s)
- [ ] Check marker positions after switching between files
- [ ] Verify waveform display shows entire file length
- [ ] Test zoom functionality after file switch
- [ ] Check segment display after file switch
- [ ] Verify playback works correctly after file switch
- [ ] Confirm no UI artifacts remain from previous files

## Hypothesis

The most likely issues are:
1. PyQtGraph may be automatically constraining the view range despite our attempts to override it
2. Downsampling may be altering time values in unexpected ways
3. The model total_time may not be being used consistently across all rendering points
4. There may be multiple entry points updating the view range that need to be synchronized
5. **New hypothesis**: Incomplete state reset when importing new files leads to inconsistent state

## Rollback Considerations

If needed, rollback should preserve:
1. Debug points we've added to understand the issue
2. The concept of passing model_total_time as the source of truth
3. Insights about the discrepancy between downsampled data and actual file length

## Code Cleanup After Implementation

After successfully implementing and testing the clean state reset approach, we should clean up the state handling code added in our previous attempt:

1. **Remove parameter passing code**:
   - Remove the `model_total_time` parameter from `update_plot` in waveform_view.py
   - Remove code that passes this parameter through rcy_controller.py and rcy_view.py
   - The clean state reset approach makes this explicit parameter passing unnecessary

2. **Simplify the waveform view code**:
   - Keep the fix in `_clamp_markers_to_data_bounds` that prevents improper constraint of markers
   - Remove any duplicated state management logic now handled by the reset mechanism
   - Consider whether explicit setting of total_time in update_slices is still needed

3. **Remove debug print statements**:
   - After verifying everything works, remove or comment out debug print statements
   - Consider keeping some critical debug points but disabled by default

4. **Document the new approach**:
   - Update comments in key methods to explain the state management approach
   - Add explanatory comments about the importance of clean state reset during file imports
   - Document any edge cases that required special handling

## Related Components

Files involved:
- `/src/python/waveform_view.py`
- `/src/python/rcy_controller.py`
- `/src/python/rcy_view.py`
- `/src/python/rcy_dispatcher.py`
- `/src/python/rcy_store.py`

Key methods to examine:
- `update_plot`
- `update_slices`
- `set_visible_range`
- `_handle_load_audio_file`

## Overarching Design Considerations

The one-way data flow architecture mandates:
1. Store should be the single source of truth
2. UI should reflect the store, not modify it directly
3. Changes flow in one direction: store → controller → view

The clean state reset approach aligns perfectly with these principles by ensuring a complete initialization sequence for any new file, just as if the application were starting from scratch.