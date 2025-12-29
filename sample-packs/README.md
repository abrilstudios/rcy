# Sample Packs

This directory contains sample pack integrations for RCY. Each subdirectory provides scripts to download, process, and register breakbeat collections as RCY presets.

## Available Packs

| Pack | Samples | Description |
|------|---------|-------------|
| [rhythm-lab](rhythm-lab/) | ~900 | Classic breakbeats from [rhythm-lab.com](https://rhythm-lab.com/breakbeats/) |

## Adding a Sample Pack

Each sample pack directory should contain:

```
sample-packs/<pack-name>/
├── README.md              # Setup instructions
├── generate_presets.py    # Script to generate config/presets_<pack>.json
├── .gitignore             # Ignore audio files and archives
└── audio/                 # Downloaded audio files (gitignored)
```

The `generate_presets.py` script should:
1. Scan the `audio/` directory for WAV files
2. Generate a `config/presets_<pack>.json` file with preset definitions
3. Each preset needs: `id`, `name`, `artist`, `file`, and `bars`

## Audio Files

Audio files are **not** included in the repository. Each pack's README contains download instructions. This keeps the repo lightweight and respects licensing.

## Usage

After setting up a pack:

```bash
just run
/presets                  # List all presets
/preset rl_amen           # Load a Rhythm Lab preset
/preset amen_classic      # Load a core preset
```

Presets from sample packs use a prefix (e.g., `rl_` for Rhythm Lab) to distinguish them from core presets.
