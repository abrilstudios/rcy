# RCY Command-Line Utilities

This directory contains convenient command-line utilities and wrappers for RCY functionality.

## Available Scripts

### SFZ Generator

`sfz-generator` - Creates SFZ instrument definitions from directories of audio files.

Usage:
```
./bin/sfz-generator -i /path/to/samples -o output.sfz [options]
```

Options:
- `-i, --input`: Directory containing audio samples (required)
- `-o, --output`: Output SFZ file path (default: output.sfz)
- `--start-key`: Starting MIDI key number (default: 36 = C1)
- `--group-id`: Optional group ID for SFZ regions
- `--extensions`: File extensions to include (default: wav)
- `-v, --verbose`: Enable verbose output

Example:
```
./bin/sfz-generator -i audio/drums -o presets/drums.sfz --start-key 36
```