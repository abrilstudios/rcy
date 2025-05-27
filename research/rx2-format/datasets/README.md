# RX2 Format Dataset

This dataset is organized for machine learning-style experimentation with RX2 file format reverse engineering.

## Dataset Structure

The dataset follows standard ML conventions with train/test/validation splits:

- **train/** - Algorithm development data (9 files)
- **test/** - Algorithm refinement data (4 files) 
- **validation/** - Blind testing data (4 files)

## Input-Output Mapping

This dataset treats RX2 format parsing as a supervised learning problem:

**Input Features**: RX2 binary files (.rx2)
- Raw binary data in Propellerhead ReCycle format
- Contains audio data and embedded user marker information
- Various breakbeat types: think, amen, apache, FBI breaks

**Output Labels**: JSON metadata describing file contents
- Marker positions and types
- Segment boundaries 
- Audio properties (duration, sample rate)
- Marker classification (user vs. auto-detected)

## Example Input-Output Pair

**Input**: `think-2-slice.rx2` (binary file)

**Expected Output**: 
```json
{
  "filename": "think-2-slice.rx2",
  "user_markers": 1,
  "total_segments": 2,
  "markers": [
    {
      "position_samples": 50651,
      "time_seconds": 1.149,
      "marker_type": "user_placed",
      "ending_pattern": "40000200"
    }
  ],
  "audio_info": {
    "duration": 2.280,
    "sample_rate": 44100,
    "total_samples": 100530
  }
}
```

## Algorithm Goal

The core algorithm should extract the JSON metadata from the binary RX2 input with 100% accuracy across all dataset files. This enables:

1. **Marker Detection**: Identify user-placed segment boundaries
2. **Audio Extraction**: Extract raw audio data for segment creation
3. **Format Understanding**: Decode RX2's internal structure
4. **Sampler Integration**: Enable RCY and other tools to work with RX2 files

## Usage in RCY

This dataset validates our ability to convert RX2 files into RCY's native format, preserving:
- User-defined segment boundaries
- Audio fidelity
- Temporal accuracy for music production workflows