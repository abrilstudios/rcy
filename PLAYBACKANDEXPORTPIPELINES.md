# RCY Playback and Export Pipelines

## Sample Accuracy in Drum and Bass: Why RCY Remembers the S1000

In most modern DAWs, tempo and pitch manipulation are handled behind the scenes—rubberbanding, granular stretch, elastic this and that. But in the world of classic jungle and drum and bass, that kind of ambiguity is dangerous. Because on a real system—a proper system—you can hear the difference.

RCY was built to fix that. It doesn't rubberband your loops or pitch-correct them with machine learning. It does what the Akai S1000 did: changes pitch and tempo by changing sample rate. That means what you hear when you stretch a break is the real deal—no interpolation, no spectral guessing. Just raw audio playing faster or slower, with all the aliasing, crunch, and movement that implies.

### Remembering the S1000 (and S950)

The S1000 made 16-bit digital playback musical by accident. You pitched things up to save RAM. You played things down to get weight. The aliasing and frequency response became part of the vibe. Even more so with the 12-bit S950, which introduced deliberate bandwidth limitation and crunchy downsampling—the exact character people now chase with plugins labeled vintage mode.

RCY isn't a plugin. It's a workflow. It keeps pitch/tempo tied to the playback engine the way the S1000 did—resampling, not stretching. When you export, it gives you back audio in the same shape you heard it. We're even looking at bringing in true 12-bit S950-style output as an export option—future work, but grounded in the same philosophy: if you can hear it, you should be able to export it.

### Why It Matters

Because in drum and bass, timing isn't just tight—it's sacred. Shifting a snare by 1 ms can kill a groove. Adding subtle phase smear from time-stretching algorithms can ruin the weight. You only get one chance to be felt on a big rig, and guesswork isn't good enough.

RCY brings back the idea that your sampler is an instrument, not a black box. That every change is deliberate. That what you hear in your headphones is what comes out the speakers—exactly.

---

This document describes the audio processing pipeline for both playback and export in RCY, explaining the design philosophy, implementation details, and technical decisions.

## Design Philosophy

RCY follows the core principle of "**what you hear is what you export**." This means:

1. Audio segments played within the application should sound identical to exported files
2. All audio transformations applied during playback are also applied during export
3. The authentic sound of hardware samplers is preserved by using sample rate adjustment for tempo/pitch changes

## Pipeline Architecture

The audio processing pipeline in RCY is modular and consists of several stages that are applied consistently for both playback and export:

```
Raw Audio
   │
   └→ [Slice Extraction] - Extract segment based on boundaries
         │
         └→ [Playback Tempo Adjustment] - Apply pitch/tempo via sample rate
              │
              └→ [Resampling] - For export only, convert to standard rate
                   │
                   └→ [Tail Fade] - Apply envelope fade processing
                        │
                        └→ Output (Export or Playback)
```

## Pipeline Stages

### 1. Slice Extraction

- Function: `extract_segment(data_left, data_right, start_sample, end_sample, is_stereo)`
- Purpose: Extracts a portion of audio from the source data based on sample boundaries
- Handles both stereo and mono audio
- Includes validation of sample ranges

### 2. Playback Tempo Adjustment

- Function: `apply_playback_tempo(segment, original_sample_rate, source_bpm, target_bpm, enabled)`
- Purpose: Applies pitch shifting via sample rate adjustment
- Calculates the ratio of target to source BPM
- Adjusts the sample rate proportionally to change playback speed and pitch
- Based on old-school sampler behavior (no time-stretching)

### 3. Resampling (Export Only)

- Function: `resample_to_standard_rate(segment, adjusted_sample_rate, target_sample_rate, is_stereo)`
- Purpose: Converts pitch-shifted audio back to a standard sample rate for compatibility
- Only applied during export, not playback
- Uses high-quality resampling algorithm to preserve audio fidelity
- Results in standard sample rate files (e.g., 44100 Hz) that still sound pitch-shifted

### 4. Tail Fade

- Function: `apply_tail_fade(segment, sample_rate, is_stereo, enabled, duration_ms, curve)`
- Purpose: Applies a fade-out envelope to the end of a segment
- Supports both linear and exponential fade curves
- Correctly handles both stereo and mono audio

## Unified Processing Function

All pipeline stages are orchestrated by a central function:

- Function: `process_segment_for_output(data_left, data_right, start_sample, end_sample, sample_rate, is_stereo, reverse, playback_tempo_enabled, source_bpm, target_bpm, tail_fade_enabled, fade_duration_ms, fade_curve, for_export, resample_on_export)`
- Purpose: Runs a segment through the entire processing pipeline
- Used by both playback and export code paths
- The `for_export` flag enables the additional resampling stage for export

## Key Implementation Details

### Resampling Method

RCY uses a fixed high-performance resampling method (kaiser_fast) during export to convert playback-rate segments back to standard sample rates (e.g. 44100 Hz). This ensures compatibility with samplers while preserving the sonic character heard during preview. The method is not configurable by design — it balances speed and fidelity and avoids unnecessary complexity.

### Tempo Adjustment vs. Time Stretching

RCY deliberately uses sample rate adjustment for tempo changes rather than time-stretching algorithms. This design choice:

1. Emulates the sound of classic hardware samplers (Akai S950, S1000, etc.)
2. Preserves transients without artifacts from time-stretching
3. Creates the characteristic "pitched-up" or "pitched-down" sound that's often desired in certain musical genres

### Import/Export Consistency

The consistent pipeline architecture ensures that exported segments will sound exactly like they did during playback within RCY. The only difference is that exported files will have a standard sample rate, making them compatible with all DAWs and hardware.

## Configuration

The audio processing pipeline is configured through `config/audio.json`:

```json
{
  "playbackTempo": {
    "enabled": false,
    "targetBpm": 120
  },
  "tailFade": {
    "enabled": false,
    "durationMs": 10,
    "curve": "exponential"
  }
}
```

## Testing

The pipeline is thoroughly tested:

1. Unit tests for each pipeline stage (`tests/test_audio_processing_pipeline.py`)
2. Integration test script for the full export workflow (`test_export_pipeline.py`)

## Technical Considerations

### Why Resample During Export?

While it would be simpler to just export at the adjusted sample rate, many DAWs and samplers:
- May not support non-standard rates like 51235 Hz
- Might resample audio to their internal rates, potentially with lower quality algorithms
- Could reject files with unusual sample rates

By performing high-quality resampling ourselves during export, we ensure:
1. Maximum compatibility
2. Consistent audio quality
3. Same sonic character as during playback

### Performance Optimization

- Playback uses direct sample rate adjustment (no resampling) for efficiency
- Export uses optimized resampling algorithms to balance quality and speed
- The `kaiser_fast` algorithm provides good quality without excessive processing time