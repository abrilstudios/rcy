# Rhythm Lab Breakbeats

**RCY is a proud sponsor of [Rhythm Lab](https://rhythm-lab.com/breakbeats/).**

This collection contains ~900 classic breakbeat samples curated over 20+ years by Rhythm Lab. From the Amen break to obscure funk gems, this is an essential resource for jungle, drum & bass, and hip-hop producers.

## Setup

### 1. Download the Archive

Visit [rhythm-lab.com/breakbeats](https://rhythm-lab.com/breakbeats/) and download the complete collection (pay-what-you-wish, €0 minimum).

### 2. Extract to Project

```bash
# Copy archive to project
cp ~/Downloads/Rhythm-lab.com\ Breakbeats\ Collection.zip \
   sample-packs/rhythm-lab/archive.zip

# Extract WAV files only
cd sample-packs/rhythm-lab
unzip -j -o archive.zip "*/WAV/*.wav" -d audio/
```

### 3. Generate Presets

```bash
python sample-packs/rhythm-lab/generate_presets.py
```

## Using the Presets

After setup, all breaks are available in RCY:

```bash
just run
/presets              # List all presets (rl_* are Rhythm Lab)
/preset rl_amen       # Load a break
```

## What's Included

~900 classic breakbeats including:

| Artist | Title |
|--------|-------|
| The Winstons | Amen Brother |
| Lyn Collins | Think (About It) |
| Incredible Bongo Band | Apache |
| James Brown | Funky Drummer |
| Bernard Purdie | Soul Drums |
| Billy Squier | Big Beat |
| Dennis Coffey | Scorpio |
| ... | ... and 890+ more |

## Directory Structure

```
sample-packs/rhythm-lab/
├── README.md              # This file
├── generate_presets.py    # Preset generation script
├── .gitignore             # Ignores archive.zip
├── archive.zip            # Downloaded archive (gitignored)
└── audio/                 # Extracted WAV files (gitignored)
    ├── The Winstons - Amen Brother.wav
    ├── James Brown - Funky Drummer.wav
    └── ...
```

## License

These are sampled fragments of released musical works. **Rights holder permission is required for commercial use.**

Audio files are not included in the repository. Download them yourself from Rhythm Lab.

## Credits

- **[Rhythm Lab](https://rhythm-lab.com/)** — 20+ years of breakbeat curation
- **RCY** — Proud sponsor
