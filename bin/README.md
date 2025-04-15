# RCY Command-Line Utilities

This directory contains convenient command-line utilities and wrappers for RCY functionality.

## Available Scripts

### RCY Application

`rcy` - Launches the main RCY (Recycling) audio application.

Usage:
```
./bin/rcy [audio_file]
```

Parameters:
- `audio_file`: Optional path to an audio file to load on startup

Example:
```
./bin/rcy audio/amen.wav
```

### SFZ Generator

`sfz-generator` - Creates SFZ instrument definitions from directories of audio files.

Usage:
```
./bin/sfz-generator -i /path/to/samples -o /path/to/samples/output.sfz [options]
```

Options:
- `-i, --input`: Directory containing audio samples (required)
- `-o, --output`: Output SFZ file path (default: output.sfz)
- `--start-key`: Starting MIDI key number (default: 36 = C1)
- `--group-id`: Optional group ID for SFZ regions
- `--extensions`: File extensions to include (default: wav)
- `-v, --verbose`: Enable verbose output

Important Notes:
- Place the output SFZ file in the ROOT DIRECTORY of your sample collection
- Works with both flat and nested sample directories
- The generator preserves the directory structure in the SFZ file

Examples:
```
# For a flat sample directory:
./bin/sfz-generator -i tal/909_Tube_Kit -o tal/909_Tube_Kit/909_kit.sfz --start-key 36

# For a nested sample library (with subdirectories):
./bin/sfz-generator -i tal/drum_samples -o tal/drum_samples/drum_kit.sfz --start-key 36
```