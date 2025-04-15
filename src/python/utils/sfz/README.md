# SFZ Utilities for RCY

This module contains utilities for working with SFZ (SFZ Format) files, which are used for creating virtual instruments that map audio samples to MIDI keys.

## SFZ Generator

The SFZ Generator is a utility that automatically creates SFZ instrument definitions from directories of audio files.

### Features

- Recursively scans directories for audio files
- Maps audio files to sequential MIDI keys
- Configurable starting MIDI key (default: 36 = C1)
- Optional group ID for SFZ regions
- Support for custom file extensions
- Cross-platform path handling

### Usage

#### Command Line

```bash
# Basic usage
python -m python.utils.sfz.generate_sfz -i /path/to/samples -o output.sfz

# Specify starting key
python -m python.utils.sfz.generate_sfz -i /path/to/samples -o output.sfz --start-key 48

# Multiple file extensions
python -m python.utils.sfz.generate_sfz -i /path/to/samples -o output.sfz --extensions wav aif mp3
```

#### From Python Code

```python
from python.utils.sfz import collect_audio_files, generate_sfz

# Collect audio files from a directory
samples = collect_audio_files('/path/to/samples')

# Generate SFZ content
sfz_content = generate_sfz(samples, start_key=36)

# Write to file
with open('instrument.sfz', 'w') as f:
    f.write(sfz_content)
```

## SFZ Format

SFZ is a simple text-based format for describing virtual instruments. Each line in an SFZ file defines a region that maps a sample to a MIDI key or range of keys.

Basic SFZ syntax:
```
<region> sample=sample.wav key=60
```

For more information about the SFZ format, visit the [SFZ Format](https://sfzformat.com/) website.