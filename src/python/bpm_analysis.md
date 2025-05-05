# BPM Calculation Analysis

## The Issue

The core issue with the tempo calculation for imported audio files is related to **measure assumptions** and not a bug in the code itself. The current formula works correctly, but assumes a specific number of measures for an audio sample.

## How the BPM is Calculated

The BPM calculation is using the following formula:
```
BPM = (60 × total_beats) / duration_in_seconds
```

Where `total_beats = measures × beats_per_measure` (assuming 4/4 time signature, so 4 beats per measure)

## Testing Results

### amen.wav (duration = 6.97s)
| Measures | BPM |
|----------|-----|
| 1        | 34.43 |
| 2        | 68.86 |
| 3        | 103.29 |
| 4        | 137.72 |
| 8        | 275.44 |
| 16       | 550.87 |

### one_track_mind_extract.wav (duration = 12.00s)
| Measures | BPM |
|----------|-----|
| 1        | 20.00 |
| 2        | 40.00 |
| 3        | 60.00 |
| 4        | 80.00 |
| 8        | 160.00 |
| 16       | 320.00 |

## Key Insights

1. The BPM calculation is working correctly, but is entirely dependent on how many measures we _assume_ are in the audio file.

2. When loading a preset, it's using the measure count from the preset_info (4 for amen_classic preset).

3. When importing a fresh audio file, it's using the current number of measures in the UI (also 4 by default).

4. The issue you reported is that "one_track_mind_extract.wav" is showing 80 BPM but that's not the actual tempo.

5. For the "one_track_mind_extract.wav" file (12 seconds), assuming:
   - 3 measures → 60 BPM
   - 4 measures → 80 BPM
   - 6 measures → 120 BPM
   - 8 measures → 160 BPM

## Conclusion

The issue isn't a bug in the code - it's an estimation problem. When importing a fresh audio file, we don't know how many measures are in it, so we're making an assumption based on the current UI value (4).

## Possible Solutions

1. **User Input**: After importing a file, prompt the user to confirm/adjust the number of measures
2. **Auto-detect**: Attempt to detect the BPM using audio analysis (beat detection)
3. **Flexible Default**: For imported files, default to 120 BPM and adjust measures accordingly
4. **Clear UI Feedback**: Make it very clear that the tempo is an estimate based on measure count

## Recommendation

For Issue #131, the fix we've implemented ensures the tempo is consistently calculated and updates when markers are moved or measures are changed. This addresses the core problem.

For the accuracy of the initial BPM estimation, we could add a follow-up issue to implement one of the above solutions (auto-detection would be ideal but more complex).