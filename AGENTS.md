# RCY for agents

RCY slices a drum break (a 44.1 kHz WAV) into equal divisions and exports the
slices as WAV files plus an SFZ instrument, a MIDI sequence and a kit manifest
that records every cut. A Textual TUI drives the same code interactively;
everything below works without it and without an audio device.

## Get a result headlessly

```bash
just setup                                            # uv sync --all-extras
just smoke                                            # slices the bundled Apache break into a temp dir
uv run rcy-export --preset apache_break --out out/apache
```

`just` is optional: `uvx --from rust-just just <recipe>` works, or read the
Justfile and run the `uv` commands directly. `just doctor` prints python,
uv, presets and audio output.

## rcy-export

```
rcy-export (--preset ID | --input FILE.wav) --out DIR [--measures N] [--resolution R] [--sfz-dialect files|offsets]
rcy-export --from-manifest KIT.rcy.json [--out DIR] [--sfz-dialect files|offsets]
```

- `--preset ID` is a key from config/presets/*.json (bundled: amen_classic,
  apache_break, apache_L, apache_R). `--measures` defaults to the preset's value.
- `--input FILE.wav` needs `--measures`. Input must be 44100 Hz.
- `--resolution R` is slices per measure (default 4), so slice count is N x R.
- `--sfz-dialect files` (default) writes one region per slice WAV. `offsets`
  writes one region per slice into the source WAV with `start=`/`end=` sample
  offsets, the form used by `presets/*/*.sfz`.
- `--from-manifest` re-renders from an existing manifest; `--out` defaults to
  the manifest's directory, so the files are rewritten in place.

Output layout for `--out DIR`:

```
DIR/001.wav ... DIR/NNN.wav     one file per slice
DIR/<basename of DIR>.sfz       <region> per slice, keys chromatic from C3 (60)
DIR/<basename of DIR>.mid       one note per slice at the computed tempo
DIR/<basename of DIR>.rcy.json  kit manifest
```

## The kit manifest and the edit loop

`<name>.rcy.json` is the record of a kit: the source WAV (relative to the
manifest), sample rate, channels, tempo, measures, the `[start, end)` sample
region, the list of cut points (`boundaries`, samples into the source), and
one entry per slice with `index`, `key` (MIDI note), `file` (rendered WAV)
and `role` (free text, empty unless set). `boundaries` is authoritative:
slice i spans `boundaries[i-1]` to `boundaries[i]`, end exclusive. Each
slice also carries `start` and `end`; they are written for readability and
ignored on load. Loading refuses a file whose slice count is not one less
than its boundary count, whose boundaries are not strictly increasing, or
whose keys fall outside 0..127.

To move a cut, edit one boundary and re-export. Moving the first cut of an
apache export 1000 samples later:

```bash
uv run rcy-export --preset apache_break --out out/apache
# in out/apache/apache.rcy.json: boundaries[1] 22050 -> 23050
uv run rcy-export --from-manifest out/apache/apache.rcy.json
```

Re-exporting an unedited manifest reproduces the slice WAVs byte for byte.
`kit_manifest.load_kit(path)` returns the manifest plus the decoded source
audio for code that wants the arrays directly.

## Where things live

- `presets/<id>/*.wav` bundled breaks; `config/presets/core.json` maps ids to files and measure counts.
- `sample-packs/` extra breaks, audio downloaded separately (see sample-packs/README.md).
- `src/python/` all code, installed flat: `from export_utils import ExportUtils`, `from kit_manifest import load_kit`.
- `tools/bin/` shell wrappers around the console scripts; `tools/bin/README.md` documents them.
- `exports/` is gitignored and a fine default output directory.

## Console scripts (installed by `just setup`)

| Script | Purpose | Needs |
|---|---|---|
| `rcy` | Textual TUI | terminal, audio output |
| `rcy-export` | headless slice + export | nothing |
| `rcy-sfz` | SFZ from a directory of WAVs | nothing |
| `rcy-midi-analyzer` | tempo and bar info from a .mid | nothing |
| `rcy-push` | hand a kit manifest to a device plugin | a plugin on PATH |

The TUI's OpenRouter agent needs the `llm` extra.

## Pushing to hardware

`rcy-push <device> --manifest KIT.rcy.json [plugin args]` looks for an
executable named `rcy-push-<device>` on PATH and runs it with the manifest and
the remaining arguments, relaying its stdout and exit code. Core ships with no
plugins and imports no MIDI backend; when nothing is found it exits 2 and names
the executable it looked for. Plugins: abrilstudios/rcy-akai (`rcy-push-s2800`,
`rcy-push-mpc`) and abrilstudios/rcy-teenage-engineering (`rcy-push-ep133`).

## Tests

```bash
just test                       # all tests, no hardware needed
just test-cov                   # with coverage
```
