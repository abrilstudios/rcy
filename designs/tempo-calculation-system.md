# Tempo Calculation System

This document describes the tempo calculation system in RCY, explaining how tempo is determined, updated, and used throughout the application.

## Core Concepts

RCY's tempo system revolves around three key components:

1. **Source BPM**: The calculated tempo based on the audio file's duration and measure count
2. **Target BPM**: The desired playback tempo that can be manually adjusted by the user
3. **Playback Ratio**: The ratio between target and source BPM that determines actual playback speed

## Tempo Calculation Formula

The fundamental formula used for tempo calculation is:

```
Tempo (BPM) = (60 × total_beats) / duration_in_seconds
```

Where:
- `total_beats` = Number of measures × Beats per measure (assumed to be 4 for 4/4 time)
- `duration_in_seconds` = Length of the audio file or selected region in seconds

## When Tempo is Calculated

Tempo is calculated or updated in several key scenarios:

### 1. Audio File Import

When importing an audio file, RCY:
- Uses the file's total duration
- Takes the current measure count (default is 4)
- Calculates the initial tempo
- Sets both `source_bpm` and `target_bpm` to this calculated value
- Enables playback tempo adjustment by default

```python
# In RcyController.load_audio_file
self.tempo = self.model.get_tempo(self.num_measures)
source_bpm = self.model.calculate_source_bpm(measures=self.num_measures)
self.target_bpm = int(round(self.tempo))
self.playback_tempo_enabled = True
```

### 2. Measure Count Changes

When the user changes the number of measures:
- Recalculates tempo with the new measure count
- Updates `target_bpm` to match the new tempo
- Enables playback tempo adjustment

```python
# In RcyController.on_measures_changed
self.num_measures = num_measures
self.tempo = self.model.get_tempo(self.num_measures)
self.target_bpm = int(round(self.tempo))
self.playback_tempo_enabled = True
```

### 3. Marker Movement

When start/end markers are moved:
- Calculates the duration between markers
- Computes a new tempo based on this duration and the current measure count
- Updates both `source_bpm` and `target_bpm` to match this new tempo

```python
# In RcyController._update_tempo_from_markers
duration = self.end_marker_pos - self.start_marker_pos
total_beats = self.num_measures * beats_per_measure
total_time_minutes = duration / 60
self.tempo = total_beats / total_time_minutes
self.target_bpm = int(round(self.tempo))
# Critical for consistent playback
self.model.source_bpm = self.tempo
```

## Playback Speed Implementation

The system adjusts playback speed by manipulating the sample rate:

1. Calculate the playback ratio:
   ```python
   ratio = target_bpm / source_bpm
   ```

2. Apply the ratio to the sample rate:
   ```python
   adjusted_sample_rate = original_sample_rate * ratio
   ```

3. Use the adjusted sample rate for playback, which effectively changes the speed without altering pitch

```python
# In audio_processor.py
def apply_playback_tempo(segment, original_sample_rate, source_bpm, target_bpm, enabled=True):
    if not enabled or target_bpm is None or source_bpm is None or source_bpm <= 0:
        return segment, original_sample_rate
    
    tempo_ratio = target_bpm / source_bpm
    adjusted_sample_rate = int(original_sample_rate * tempo_ratio)
    
    return segment, adjusted_sample_rate
```

## UI Interaction

Users interact with the tempo system through several UI elements:

1. **Measure Input Field**: Allows adjusting the number of measures in the audio file
2. **Tempo Display**: Shows the calculated tempo based on current settings
3. **Playback Tempo Controls**:
   - **Checkbox**: Enables/disables tempo adjustment
   - **Dropdown**: Provides preset BPM values
   - **Custom Input**: Allows entering a specific BPM value

When users change these values, the system:
- Updates the internal model state
- Recalculates tempo and playback ratios
- Updates UI elements to reflect the new state
- Applies the new tempo settings to playback

## Examples

### Example 1: 12-second Audio File

For a 12-second audio file with 4 measures:
- Total beats = 4 measures × 4 beats/measure = 16 beats
- BPM = (60 × 16) / 12 = 80 BPM

If the user selects only half the file by moving markers:
- Duration = 6 seconds
- BPM = (60 × 16) / 6 = 160 BPM

### Example 2: Playback Speed Adjustment

If a file has:
- Source BPM = 80
- Target BPM = 120

The playback ratio would be:
- Ratio = 120 / 80 = 1.5
- This means the file will play at 1.5× speed

## Technical Implementation Notes

The system spans several classes:

1. **WavAudioProcessor** (model):
   - Stores `source_bpm`
   - Provides methods to calculate tempo
   - Handles playback with adjusted sample rate

2. **RcyController** (controller):
   - Manages the current tempo value
   - Stores `target_bpm` and `playback_tempo_enabled` state
   - Coordinates between model and view

3. **RcyView** (view):
   - Provides UI controls for tempo adjustment
   - Displays calculated tempo
   - Sends signals when user interacts with tempo controls

## Recent Improvements

Recent fixes to the tempo system ensure:

1. The `calculate_source_bpm` method consistently returns the class property
2. When markers are moved, both `source_bpm` and `target_bpm` are updated
3. Marker drag events are properly connected to tempo recalculation
4. UI elements are consistently updated to reflect the current tempo state

These improvements ensure that tempo calculation works consistently regardless of how users interact with the application, whether loading files, changing measures, or moving markers.