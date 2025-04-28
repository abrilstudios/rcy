# Stereo to Mono Conversion Feature

## Overview

This design document outlines the implementation of a new feature that allows users to convert stereo audio files to mono using either the left or right channel exclusively. This feature addresses issue #90 and provides more flexibility in audio manipulation.

## Current Implementation

Currently, RCY handles stereo and mono audio as follows:

1. **Audio Detection**:
   - `WavAudioProcessor` detects if a file is stereo or mono based on the number of channels
   - Sets `self.is_stereo = self.channels > 1` during file loading

2. **Data Storage**:
   - For stereo files, `data_left` and `data_right` contain separate channel data
   - For mono files, the same data is duplicated to both `data_left` and `data_right` for consistency

3. **Display**:
   - UI display mode depends on the `stereo_display` setting in the configuration
   - Waveform view supports both stereo (dual waveform) and mono (single waveform) display modes

## Implementation Requirements

The implementation will add:

1. Two new menu options to convert stereo to mono using:
   - Left channel only
   - Right channel only

2. Supporting methods in the model and controller layers to handle the conversion process

3. UI feedback to indicate when conversion has been applied

## Technical Design

### 1. Audio Processing Layer

Add a new method to `WavAudioProcessor` to handle the conversion:

```python
def convert_to_mono(self, use_channel='left'):
    """Convert stereo audio to mono using specified channel
    
    Args:
        use_channel (str): Which channel to use - 'left', 'right', or 'mix'
        
    Returns:
        bool: True if conversion was performed, False if already mono
    """
    # Only process if actually stereo
    if not self.is_stereo:
        return False
        
    if use_channel == 'left':
        # Use only left channel
        mono_data = self.data_left
    elif use_channel == 'right':
        # Use only right channel
        mono_data = self.data_right
    else:
        # Default mix (for future expansion)
        mono_data = (self.data_left + self.data_right) / 2
        
    # Update data arrays
    self.data_left = mono_data
    self.data_right = mono_data
    
    # Update metadata
    self.is_stereo = False
    self.channels = 1
    
    # Return True to indicate successful conversion
    return True
```

### 2. Controller Layer

Add a new method to `RcyController` to handle the UI action:

```python
def convert_to_mono(self, use_channel='left'):
    """Convert stereo audio to mono
    
    Args:
        use_channel (str): Which channel to use - 'left' or 'right'
    """
    # Convert audio in the model
    conversion_applied = self.model.convert_to_mono(use_channel)
    
    if conversion_applied:
        # Update the view
        self.update_view()
        
        # Show notification
        channel_name = "left" if use_channel == 'left' else "right"
        self.view.show_status_message(f"Audio converted to mono using {channel_name} channel")
    else:
        # Already mono, show message
        self.view.show_status_message("Audio is already mono")
```

### 3. UI Layer

Add new menu options to the Options menu in `RcyView.create_menu_bar()`:

```python
# Audio Channels submenu
audio_channels_menu = options_menu.addMenu("Audio Channels")

# Convert to mono (left) action
mono_left_action = QAction("Convert to Mono (Left Channel)", self)
mono_left_action.setStatusTip('Convert stereo to mono using left channel only')
mono_left_action.triggered.connect(lambda: self.controller.convert_to_mono('left'))
audio_channels_menu.addAction(mono_left_action)

# Convert to mono (right) action
mono_right_action = QAction("Convert to Mono (Right Channel)", self)
mono_right_action.setStatusTip('Convert stereo to mono using right channel only')
mono_right_action.triggered.connect(lambda: self.controller.convert_to_mono('right'))
audio_channels_menu.addAction(mono_right_action)
```

### 4. Status Display

Add a status message method to `RcyView` if not already present:

```python
def show_status_message(self, message, timeout=3000):
    """Show a message in the status bar
    
    Args:
        message (str): Message to display
        timeout (int): Duration in milliseconds (default 3 seconds)
    """
    self.statusBar().showMessage(message, timeout)
```

## Menu Structure

The new options will be integrated into the menu structure as follows:

```
Options
├── Playback Tempo
├── Playback Mode
└── Audio Channels            [new submenu]
    ├── Convert to Mono (Left Channel)
    └── Convert to Mono (Right Channel)
```

## User Experience

1. User loads a stereo audio file
2. User selects "Options > Audio Channels > Convert to Mono (Left Channel)"
3. The system converts the stereo audio to mono using only the left channel
4. The waveform display updates to show the new mono audio
5. A status message confirms the conversion

## Implementation Considerations

1. **Undo Support**:
   - In a future version, this operation could be made undoable by storing the original stereo data

2. **Performance**:
   - The conversion is lightweight and should be nearly instantaneous for most audio files

3. **Persistence**:
   - The conversion is applied in memory
   - The changes will only be saved permanently if the user exports or saves the session

4. **UI State**:
   - The menu items should be disabled if the audio is already mono
   - This could be implemented by updating menu item state when loading files

## Testing Plan

1. **Unit Tests**:
   - Test the `convert_to_mono` method with stereo files
   - Verify that the metadata (`is_stereo` and `channels`) is updated correctly
   - Verify that both `data_left` and `data_right` contain the correct data after conversion

2. **UI Tests**:
   - Verify that the menu items are present and work correctly
   - Verify that the status message is displayed

3. **Integration Tests**:
   - Verify that waveform display updates correctly after conversion
   - Verify that subsequent processing (segmentation, export) works correctly with converted audio