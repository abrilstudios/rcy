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
- Generates sampler-compatible SFZ files

### Important File Structure Notes

For best compatibility with samplers (like TAL Sampler, Logic EXS24, etc.):

1. **Place the output SFZ file in the ROOT DIRECTORY of your sample collection**
2. The generator preserves the directory structure in the SFZ file
3. Works with both flat directories and nested sample libraries
4. For maximum compatibility, avoid spaces and special characters in filenames

### Usage

#### Command Line

```bash
# Basic usage
python -m python.utils.sfz.generate_sfz -i /path/to/samples -o /path/to/samples/output.sfz

# Specify starting key
python -m python.utils.sfz.generate_sfz -i /path/to/samples -o /path/to/samples/output.sfz --start-key 48

# Multiple file extensions
python -m python.utils.sfz.generate_sfz -i /path/to/samples -o /path/to/samples/output.sfz --extensions wav aif mp3
```

### Recommended Workflow

1. **Prepare your samples**: Place all samples in a dedicated directory
2. **Generate the SFZ file**: Run the generator and output the SFZ file to the same directory
3. **Load in your sampler**: Load the SFZ file in your sampler of choice

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