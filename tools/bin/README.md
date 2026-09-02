# RCY Command-Line Utilities

This directory contains convenient command-line utilities and wrappers for RCY functionality.

## Available Scripts

Every wrapper here runs inside the uv environment created by `just setup`,
so they work from any directory without activating anything. The Python entry
points they call (`rcy`, `rcy-export`, `rcy-sfz`, `rcy-push`, `rcy-midi-analyzer`)
are also available as `uv run <name>`.

### Headless export

`uv run rcy-export` slices a preset or a 44.1 kHz WAV and writes WAV slices,
an SFZ and a MIDI file. See AGENTS.md at the repo root for flags and output layout.

### MP3 Extract

`mp3extract` - Extracts a portion of an MP3 file to WAV format.

Usage:
```
tools/bin/mp3extract input.mp3 start_time end_time --outfile=output.wav [--samplerate=44100]
```

Parameters:
- `input.mp3`: Path to the MP3 file to extract from (required)
- `start_time`: Start time for extraction (format: HH:MM:SS, MM:SS, or SS) (required)
- `end_time`: End time for extraction (format: HH:MM:SS, MM:SS, or SS) (required)
- `--outfile`: Path to output WAV file (required)
- `--samplerate`: Sample rate of output file in Hz (default: 44100)

Example:
```
tools/bin/mp3extract mp3/pulp_fiction_paul_hardcastle.mp3 0:23 0:26 --outfile=wav/pulp_fiction_snippet.wav
```

### SFZ Generator

`sfz-generator` - Creates SFZ instrument definitions from directories of audio files.

Usage:
```
tools/bin/sfz-generator -i /path/to/samples -o /path/to/samples/output.sfz [options]
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
tools/bin/sfz-generator -i tal/909_Tube_Kit -o tal/909_Tube_Kit/909_kit.sfz --start-key 36

# For a nested sample library (with subdirectories):
tools/bin/sfz-generator -i tal/drum_samples -o tal/drum_samples/drum_kit.sfz --start-key 36
```