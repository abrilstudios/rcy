# RCY Segment Architecture Design

## Overview

RCY's segment system enables users to slice audio into smaller pieces for manipulation and playback. This document analyzes the current architecture to understand why keyboard shortcuts have off-by-one errors and how the segment system works holistically.

## Core Concepts

### Segments vs Slices vs Markers

- **Segments**: The actual audio regions that can be played independently
- **Slices**: The boundary points (sample positions) that define where segments begin/end  
- **Markers**: UI indicators showing current selection (start/end markers)

### Data Representation

```
Audio:     [====================audio data====================]
Slices:         |    |    |    |    |    (boundary points)
Segments:   [1] | [2]| [3]| [4]| [5]| [6] (playable regions)
```

**Key Principle**: N slice boundaries create N+1 segments

## Architecture Components

### 1. Audio Processor (`audio_processor.py`)

**Primary Role**: Core segment storage and calculation

**Key Data**:
- `self.segments`: Array of slice boundaries (sample positions)
- `self.sample_rate`: For sample-to-time conversion

**Key Methods**:
- `split_by_measures(resolution)`: Creates equal-time segments
- `split_by_transients()`: Uses AI-based onset detection  
- `get_segment_boundaries(click_time)`: Finds segment containing click

**Segment Creation Logic**:
```python
# split_by_measures creates:
total_divisions = measures * resolution
self.segments = [int(i * samples_per_division) for i in range(total_divisions + 1)]
# Result: [0, boundary1, boundary2, ..., total_samples]
```

### 2. Controller (`rcy_controller.py`)

**Primary Role**: Coordinate between UI and audio processing

**Key Data**:
- `current_slices`: Time-based slice positions (seconds)
- Converts between sample and time domains

**Key Methods**:
- `get_segment_boundaries(click_time)`: Click-to-segment mapping
- `play_segment(start_time, end_time)`: Orchestrates playback

**Boundary Calculation Logic**:
```python
# For click at time T, find segment containing T
for i, segment in enumerate(segments):
    if click_sample < segment:
        if i == 0: return 0, segment_time
        else: return segments[i-1]_time, segment_time
```

### 3. View (`rcy_view.py`)

**Primary Role**: Handle UI interactions and keyboard shortcuts

**Key Data**:
- `SEGMENT_KEY_MAP`: Maps keyboard keys to 1-based segment indices

**Key Methods**:
- `_play_segment_by_index(segment_index)`: Direct index-to-segment playback
- `window_key_press()`: Keyboard event handling

**Index Calculation Logic**:
```python
# For 1-based segment index K:
if segment_index == 1: 
    return [0, segments[0]] or [0, segments[1]] if segments[0]==0
elif segment_index <= len(segments):
    return [segments[K-2], segments[K-1]]
else:
    return [segments[-1], data_length]
```

## Data Flow Patterns

### Click-Based Playback
```
User clicks waveform 
→ waveform_view.py detects click 
→ controller.get_segment_boundaries() 
→ finds containing segment via search
→ controller.play_segment()
```

### Keyboard-Based Playback  
```
User presses key "2"
→ rcy_view.py maps to segment index 2
→ _play_segment_by_index() calculates boundaries directly
→ controller.play_segment()
```

## The Off-by-One Problem

### Root Cause Analysis

The architecture reveals **two independent segment calculation systems**:

1. **Click detection**: Uses time-based search through `current_slices`
2. **Keyboard shortcuts**: Uses array index calculation from `segments`

### Critical Inconsistency

The keyboard shortcut logic has special handling for `segments[0] == 0`:

```python
if segment_index == 1:
    start_sample = 0
    if len(segments) > 1 and segments[0] == 0:
        end_sample = segments[1]  # Skip first boundary!
    else:
        end_sample = segments[0]  # Use first boundary
```

This creates different behavior based on whether the first slice boundary is at sample 0.

### Expected vs Actual Behavior

**When segments = [0, 1000, 2000, 3000]:**

| Method | Key "1" Should Play | Key "1" Actually Plays | Issue |
|--------|--------------------|--------------------|-------|
| Click | [0, 1000] | [0, 1000] | ✅ Correct |
| Keyboard | [0, 1000] | [0, 2000] | ❌ **Skips to segments[1]** |

**When segments = [1000, 2000, 3000]:**

| Method | Key "1" Should Play | Key "1" Actually Plays | Issue |
|--------|--------------------|--------------------|-------|
| Click | [0, 1000] | [0, 1000] | ✅ Correct |
| Keyboard | [0, 1000] | [0, 1000] | ✅ Correct |

## Proposed Solutions

### Option 1: Unify Through Controller (Recommended)

Make keyboard shortcuts use the same `get_segment_boundaries()` logic:

```python
def _play_segment_by_index(self, segment_index):
    # Convert index to approximate time, then use existing logic
    segments = self.controller.model.get_segments()
    if segment_index <= 0 or segment_index > len(segments) + 1:
        return
    
    # Calculate midpoint time of target segment
    if segment_index == 1:
        target_time = 0.0  # Always click at start for first segment
    else:
        # Click in middle of target segment
        start_boundary = segments[segment_index - 2] / sample_rate
        end_boundary = segments[segment_index - 1] / sample_rate  
        target_time = (start_boundary + end_boundary) / 2
    
    # Use existing controller logic
    start_time, end_time = self.controller.get_segment_boundaries(target_time)
    self.controller.play_segment(start_time, end_time)
```

### Option 2: Fix Index Calculation

Remove special case handling and use consistent 0-based indexing:

```python
def _play_segment_by_index(self, segment_index):
    # Convert 1-based UI index to 0-based array index
    array_index = segment_index - 1
    
    if array_index == 0:
        return [0, segments[0]]
    elif array_index < len(segments):
        return [segments[array_index-1], segments[array_index]]
    else:
        return [segments[-1], data_length]
```

### Option 3: Architectural Refactor

Create a unified `SegmentManager` class that both UI and controller use:

```python
class SegmentManager:
    def get_segment_boundaries(self, segment_index_or_time):
        # Unified logic for both index and time-based access
        
    def get_segment_at_time(self, time):
        # Click-based access
        
    def get_segment_at_index(self, index):
        # Keyboard-based access
```

## Testing Strategy

To validate any fix, ensure these behaviors are consistent:

1. **Visual consistency**: Clicking in segment N should play same audio as pressing key N
2. **Index consistency**: `_play_segment_by_index(2)` should play the second visual segment
3. **Boundary consistency**: Both methods should return identical time ranges for same segment

## Conclusion

The off-by-one errors stem from architectural inconsistency between two parallel segment calculation systems. The fix requires either unifying the systems or ensuring they produce identical results for the same logical segments.

The root issue is not in the index math, but in having **two different sources of truth** for segment boundaries that can produce different results for the same user intent.