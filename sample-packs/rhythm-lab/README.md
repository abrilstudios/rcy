# Rhythm Lab Breakbeats Sample Pack

Classic breakbeat samples from [rhythm-lab.com/breakbeats](https://rhythm-lab.com/breakbeats/).

## Setup

### Quick Start

```bash
# Download all breakbeats and create presets
python sample-packs/rhythm-lab/setup.py

# Or just download specific breaks (by ID pattern)
python sample-packs/rhythm-lab/setup.py --id amen
python sample-packs/rhythm-lab/setup.py --id funky_drummer
python sample-packs/rhythm-lab/setup.py --id apache
```

### List Available Breakbeats

```bash
python sample-packs/rhythm-lab/setup.py --list
```

### Using the Presets

After setup, presets will be available in RCY:

```bash
# GUI
just run
# Then use File > Presets or the preset selector

# TUI
just tui
/presets              # List all presets (including rl_* rhythm lab ones)
/preset rl_amen       # Load a rhythm lab preset
```

## What's Included

The manifest includes 48 classic breakbeats:

| ID | Artist | Title |
|----|--------|-------|
| `amen_winstons` | The Winstons | Amen Brother |
| `think_lyn_collins` | Lyn Collins | Think (About It) |
| `apache_incredible` | Incredible Bongo Band | Apache |
| `funky_drummer` | James Brown | Funky Drummer |
| `impeach_president` | The Honey Drippers | Impeach The President |
| `soul_drums_1` | Bernard Purdie | Soul Drums |
| `big_beat` | Billy Squier | Big Beat |
| `scorpio_cd` | Dennis Coffey | Scorpio |
| `assembly_line_1` | Commodores | Assembly Line |
| ... | ... | ... |

See `manifest.json` for the complete list.

## Directory Structure

```
sample-packs/rhythm-lab/
├── README.md          # This file
├── manifest.json      # Breakbeat metadata
├── setup.py           # Download & preset creation script
└── audio/             # Downloaded .wav files (gitignored)
    ├── The Winstons - Amen Brother.wav
    ├── James Brown - Funky Drummer.wav
    └── ...
```

## License

These are sampled fragments of released musical works. **Rights holder permission is required for commercial use.**

The audio files are not included in this repository. You must download them yourself using the setup script.

## Adding More Breakbeats

Edit `manifest.json` to add more breakbeats:

```json
{
  "id": "my_break",
  "filename": "Artist - Song Title.wav",
  "artist": "Artist",
  "title": "Song Title",
  "measures": 2
}
```

Then run `setup.py` again to download and create presets.
