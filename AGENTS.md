# RCY for agents

RCY slices a drum break (a 44.1 kHz WAV) into equal divisions and exports the
slices as WAV files plus an SFZ instrument and a MIDI sequence. A Textual TUI
drives the same code interactively; everything below works without it.

## Get a result headlessly

```bash
just setup                                            # uv sync --all-extras
just smoke                                            # slices the bundled Apache break into a temp dir
uv run rcy-export --preset apache_break --out out/apache
```

`just` is optional: `uvx --from rust-just just <recipe>` works, or read the
Justfile and run the `uv` commands directly. `just doctor` prints python,
uv, presets, audio output and MIDI ports.

## rcy-export

```
rcy-export (--preset ID | --input FILE.wav) --out DIR [--measures N] [--resolution R]
```

- `--preset ID` is a key from config/presets/*.json (bundled: amen_classic,
  apache_break, apache_L, apache_R). `--measures` defaults to the preset's value.
- `--input FILE.wav` needs `--measures`. Input must be 44100 Hz.
- `--resolution R` is slices per measure (default 4), so slice count is N x R.

Output layout for `--out DIR`:

```
DIR/001.wav ... DIR/NNN.wav   one file per slice
DIR/<basename of DIR>.sfz     <region> per slice, keys chromatic from C3 (60)
DIR/<basename of DIR>.mid     one note per slice at the computed tempo
```

The process opens an audio output stream while slicing, so a machine with no
output device fails at start. `just doctor` shows the device it would use.

## Where things live

- `presets/<id>/*.wav` bundled breaks; `config/presets/core.json` maps ids to files and measure counts.
- `sample-packs/` extra breaks, audio downloaded separately (see sample-packs/README.md).
- `src/python/` all code, installed flat: `from s2800 import S2800`, `from export_utils import ExportUtils`.
- `tools/bin/` shell wrappers around the console scripts; `tools/bin/README.md` documents them.
- `exports/` is gitignored and a fine default output directory.

## Console scripts (installed by `just setup`)

| Script | Purpose | Needs |
|---|---|---|
| `rcy` | Textual TUI | terminal, audio output |
| `rcy-export` | headless slice + export | audio output |
| `rcy-sfz` | SFZ from a directory of WAVs | nothing |
| `rcy-midi-analyzer` | tempo and bar info from a .mid | nothing |
| `rcy-s2800-agent` | Akai S2800 SysEx spec lookup; device read/write | MIDI + S2800 for device commands |
| `rcy-s2800` | upload/list/delete samples on an S2800 | MIDI + S2800 |
| `rcy-mpc` | upload samples to an MPC2000XL over SDS | MIDI + MPC |

Hardware paths need the `hardware` extra (python-rtmidi), included in
`just setup`. `just agent-start` needs the `agent` extra and credentials in
`.env` (see `.env.example`). The TUI's OpenRouter agent needs the `llm` extra.

## Tests

```bash
just test                       # 259 tests, hardware tests deselected
uv run pytest -m s2800          # S2800 tests, device connected
uv run pytest -m ep133          # EP-133 tests, device connected
just test-cov                   # with coverage
```
