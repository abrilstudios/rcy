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
uv, presets, audio output and MIDI ports.

## rcy-export

```
rcy-export (--preset ID | --input FILE.wav) --out DIR [--measures N] [--resolution R | --cuts CUTS]
           [--onsets] [--snap-onsets [MS]] [--grid-offset MS] [--sfz-dialect files|offsets] [--render] [--json]
rcy-export --from-manifest KIT.rcy.json [--out DIR] [--onsets] [--snap-onsets [MS]] [--sfz-dialect files|offsets] [--render] [--json]
```

- `--preset ID` is a key from config/presets/*.json (bundled: amen_classic,
  apache_break, apache_L, apache_R). `--measures` defaults to the preset's value.
- `--input FILE.wav` needs `--measures`. Input must be 44100 Hz.
- `--resolution R` is slices per measure (default 4) for an equal chop.
- `--cuts CUTS` slices at the cuts in a cut list instead (`-` reads stdin);
  see below.
- `--onsets` runs onset detection, records the onsets in the manifest and
  adds an `onset_ms` column to the table.
- `--snap-onsets [MS]` moves every cut except the first and last to MS ms
  (default 3) before the nearest onset when one lies within half a
  sixteenth; a cut with no onset that close stays put and a warning names
  it on stderr. Implies `--onsets`. Applies to cut lists and equal chops.
- `--grid-offset MS` starts the bar grid MS ms into the file. Beat positions
  in cut lists and in the table, and the interior cuts of an equal chop,
  shift with it. The value is stored in the manifest as `grid_offset`.
- `--sfz-dialect files` (default) writes one region per slice WAV. `offsets`
  writes one region per slice into the source WAV with `start=`/`end=` sample
  offsets, the form used by `presets/*/*.sfz`, and does not write slice
  WAVs unless `--render` is given.
- `--from-manifest` re-renders from an existing manifest; `--out` defaults to
  the manifest's directory, so the files are rewritten in place. It refuses
  `--cuts`, `--measures`, `--resolution` and `--grid-offset`.
- `--json` prints the report below as one JSON document.

Output layout for `--out DIR`:

```
DIR/001.wav ... DIR/NNN.wav     one file per slice (files dialect, or --render)
DIR/<basename of DIR>.sfz       <region> per slice, keys chromatic from C3 (60), `// role` per region
DIR/<basename of DIR>.mid       one note per slice at the computed tempo, role as a text event on the note
DIR/<basename of DIR>.rcy.json  kit manifest
```

Every export prints the source, tempo, slice count (with the per-measure
resolution only for equal chops), the onset count when onsets are known,
the output paths, and one row per slice: index, key, role, start sample,
nearest sixteenth as `bar.beat.sixteenth`, signed ms from that sixteenth,
length in sixteenths, and with onsets the signed ms from the cut to the
nearest onset (3.0 after `--snap-onsets`).

### Cut lists

One cut per line: a position, then an optional role that runs to the end
of the line. A position is samples (`19388`), seconds (`0.44s`) or beats
(`bar.beat` or `bar.beat.sixteenth`, all 1-based, so `1.3.3` is the "and"
of beat 3 in bar 1). Blank lines and `#` comments are skipped. A cut at 0
is implied when the first cut is later; the end of the file is always the
last boundary. Cuts must increase.

From a cut list to a kit in two commands, using the 12-cell Amen chop in
`tests/fixtures/amen_classic_chops.cuts`:

```bash
uv run rcy-onsets --preset amen_classic          # where the hits are, as bar.beat.sixteenth
uv run rcy-export --preset amen_classic --cuts tests/fixtures/amen_classic_chops.cuts \
    --snap-onsets --out out/amen
```

The cut list reads:

```
1.1     b1 kicks
1.2     b1 snare cell
1.3.3   b1 turnaround
1.4     b1 snare 4 cell
2.1     b2 full bar
3.1     b3 kicks
3.2     b3 snare cell
3.3.3   b3 kick 3+ long
3.4.3   b3 displaced snare
4.1.3   b4 kicks
4.2     b4 snare cell
4.3.3   b4 crash phrase
```

and the export prints, among the other rows:

```
#   key  role                start   beat   grid_ms  16ths  onset_ms
2   61   b1 snare cell       19388   1.2.1  4.0      6.02   3.0
3   62   b1 turnaround       48316   1.3.3  6.4      1.95   3.0
```

Every hit in amen.wav trails the sample-zero grid by 15 to 30 ms, which is
why the snap matters: without it each slice starts with the tail of the
previous hit.

## rcy-onsets

```
rcy-onsets (--preset ID | --input FILE.wav) [--measures N] [--grid-offset MS] [--json]
```

Prints every detected onset with its sample offset, seconds, nearest
sixteenth as `bar.beat.sixteenth` and the signed ms from that sixteenth.
The detector is librosa's onset strength and peak picker on the left
channel with a 64-sample hop, backtracked to the attack; `rcy-export
--onsets` and `--snap-onsets` use the same one, and the TUI's transient
split uses it at frame resolution.

## The kit manifest and the edit loop

`<name>.rcy.json` is the record of a kit: the source WAV (relative to the
manifest), sample rate, channels, tempo, measures, the `[start, end)` sample
region, the list of cut points (`boundaries`, samples into the source), and
one entry per slice with `index`, `key` (MIDI note), `file` (rendered WAV)
and `role` (free text, empty unless set). `boundaries` is authoritative:
slice i spans `boundaries[i-1]` to `boundaries[i]`, end exclusive. Each
slice also carries `start` and `end`; they are written for readability and
ignored on load. Two optional keys: `onsets`, the detected onsets in
samples (present after `--onsets` or `--snap-onsets`), and `grid_offset`,
samples, where the bar grid starts (present when not 0). Neither changes
how the file is sliced. Loading refuses a file whose slice count is not one
less than its boundary count, whose boundaries are not strictly increasing,
or whose keys fall outside 0..127.

To move a cut, edit one boundary and re-export. Moving the first cut of an
apache export 1000 samples later:

```bash
uv run rcy-export --preset apache_break --out out/apache
# in out/apache/apache.rcy.json: boundaries[1] 22050 -> 23050
uv run rcy-export --from-manifest out/apache/apache.rcy.json
```

To snap the cuts of an existing kit to its hits, add `--snap-onsets` to the
`--from-manifest` command; it uses the manifest's `onsets` when present and
detects them otherwise.

Re-exporting an unedited manifest reproduces the slice WAVs byte for byte.
`kit_manifest.load_kit(path)` returns the manifest plus the decoded source
audio for code that wants the arrays directly.

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
| `rcy-export` | headless slice + export | nothing |
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
just test                       # 311 tests, hardware tests deselected
uv run pytest -m s2800          # S2800 tests, device connected
uv run pytest -m ep133          # EP-133 tests, device connected
just test-cov                   # with coverage
```
