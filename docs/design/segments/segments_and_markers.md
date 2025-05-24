# Segments and Markers in RCY

This document explains the current design and behavior of segments and markers in the RCY application.

## Core Concepts

### Segments and Slices
- Segments are created either by splitting at transients or by measure divisions
- These are stored as sample indices in `model.segments`
- When you click in the waveform, the app determines which segment contains the click and plays that segment
- The controller uses `get_segment_boundaries()` to convert a click time to segment boundaries

### Start and End Markers
- The start and end markers are distinct from the segment system
- They're visual markers that users can set independently of segments
- When spacebar is pressed, if both markers are set, the app plays from start to end marker

## Interaction Between Systems

### Independence of Markers and Segments
- There is no direct link in the code between the start/end markers and the segment boundaries
- When slices are updated via `update_slices()`, the markers are preserved rather than reset
- The segment system doesn't automatically adjust to accommodate marker positions

### Playback Behavior
- Controller's `play_segment(click_time)` method gets segment boundaries for the click location
- For the first segment, the start boundary is 0, regardless of the start marker's position
- For the last segment, the end boundary is the total audio duration, regardless of the end marker's position

## Design Implications

The key design point is that **segments and markers operate independently**. Moving the start marker does not affect where the first segment begins, and moving the end marker does not affect where the last segment ends.

This has implications for features that might need to consider both systems:

1. For loop mode:
   - Looping must loop between markers (like spacebar playback does) going from start to end and back to start.

2. For exporting:
   - All segments from 0 to sample end (not marker end) should be included. 

## User Experience 

The current behavior creates two different playback models:
- Click on waveform: Plays just the segment that was clicked
- Press spacebar: Plays from start marker to end marker

This dual approach gives users flexibility, but may also create confusion if the mental model isn't clear.

## Future Considerations

Any future changes to this design should carefully consider:
1. Impact on user expectations and mental model
2. Consistency across different interactions
3. Backwards compatibility with existing projects
4. Whether to more tightly couple markers and segments or maintain their independence

The decision to change this behavior should be made after gathering user feedback and considering use cases that rely on the current implementation.
