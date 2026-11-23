# rcy

rcy cuts a drum break into a sampler kit. It has two programs: `rcy-export`,
a command-line program that writes the kit, and `rcy-window`, a single window
where a person places the cuts by eye and ear. An agent or a script starts
both with a complete command line; the window asks the person for nothing the
command line could have said.

This is an alpha. The file formats and command lines can still change.

## What a kit is

`rcy-export` writes one directory:

| File | Contents |
|---|---|
| `001.wav`, `002.wav`, ... | One WAV per slice, copied from the source without resampling, fades or gain change. |
| `<name>.sfz` | An SFZ instrument, one region per slice from MIDI key 60 upward. |
| `<name>.exs` | With `--exs`, a Logic Pro Sampler instrument. |
| `<name>.mid` | A MIDI file that plays the slices in order at the break's tempo. |
| `<name>.rcy.json` | The manifest: source, tempo, cut positions in frames, and each slice's key and file. |

The manifest is the editable form of a kit. The window reads and writes it,
and `rcy-export --from-manifest` cuts the kit again from it.

Sources are 16-bit WAV at 44.1 kHz, mono or stereo. Tempo comes from the
length of the break and its measure count; nothing is time-stretched.

## Requirements

- Node.js 22 or later for `rcy-export`.
- Electron 33 for `rcy-window`, installed by `npm ci --prefix tools/window-runtime`.
  The window is built and tested on macOS.

## Cutting a kit

```
RCY_PRESETS=presets node export/rcy-export --preset amen_classic --out /tmp/amen --exs
node export/rcy-export --input break.wav --measures 2 --resolution 8 --out /tmp/kit
node export/rcy-export --from-manifest /tmp/kit/kit.rcy.json --out /tmp/kit2 --buffer-ms 20
```

`--measures` is the length of the break in 4/4 measures and `--resolution` the
number of equal slices per measure. `--preset` reads the catalog directory
named by `RCY_PRESETS`.

`--buffer-ms N` keeps N milliseconds of source audio either side of each
slice in its file and writes the slice's start and end points into the SFZ
and EXS instruments. A cut placed a few milliseconds into a hit then loses
nothing, and the points stay adjustable in the sampler. Without the option a
file holds exactly its slice.

`SPEC.md` states every option, file format rule and refusal message.

## Placing cuts in the window

```
electron window/rcy-window --manifest kit.rcy.json --record run.json --out edited.rcy.json \
    --split transients --sensitivity 72 \
    --task "Put one cut at the start of every hit you want on its own pad."
```

`electron` is `tools/window-runtime/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron`
after the install above.

The command line states the run: the manifest to open, the first-pass split
the window performs at startup (`--split measures` with `--resolution`, or
`--split transients` with `--sensitivity`), the view and selection, the task
shown to the person, where the result is written, and with `--expect-slices`
the slice count the result must have before Save is available.

In the window a click plays a slice, a drag moves a cut, a double-click adds
or removes one, and the wheel or `=` and `-` zoom down to single frames.

| Exit code | Meaning |
|---|---|
| 0 | Saved: the manifest was written to `--out`. |
| 3 | Closed without saving. |
| 2 | Refused at launch; the reason is on stderr. |

Every run writes the file named by `--record`: the arguments, the opening
state, each edit, undo, redo and audition with its time, the final cuts and
the exit code. The records are the history of what a person changed and are
meant to be kept.

`WINDOW.md` states the window's behaviour, keys and controls.

## A whole task

```
node export/rcy-export --input break.wav --measures 4 --resolution 1 --out work/source
electron window/rcy-window --manifest work/source/source.rcy.json --split measures --resolution 8 \
    --task "Move each cut onto its hit." --out work/edited.rcy.json --record work/run.json
node export/rcy-export --from-manifest work/edited.rcy.json --out work/kit --exs --buffer-ms 20
```

The second command returns when the person saves or closes, so the third
runs only on exit code 0.

## Layout

| Path | Contents |
|---|---|
| `SPEC.md`, `WINDOW.md` | The behaviour of the two programs. They are kept in step with the code. |
| `export/main.js`, `window/main.js` | The programs' sources. |
| `export/rcy-export`, `window/rcy-window` | The programs as run: each is the SDK followed by its source, in one file. |
| `rcy-sdk/` | The code for every file format (WAV, MIDI, SFZ, EXS, manifest), with its tests and `dist/bundle.cjs`, which builds a program file. |
| `presets/` | The preset catalog and its audio. |
| `features/` | Acceptance scenarios: Gherkin for `rcy-export`, a Playwright script for the window. |
| `harness/`, `bin/` | Step definitions and tooling for the Gherkin scenarios and for generating `rcy-export` from `SPEC.md` with a coding agent. |
| `INVARIANTS.md`, `VALIDATION.md`, `BASELINE.md`, `DEFERRED.md` | Rules and records for that generation process. |
| `research/` | Notes on the behaviour of the earlier Python application. |
| `hardware/` | MIDI tools for the Akai S2800, the MPC2000XL and the EP-133. See `hardware/README.md`. |

## Changing the programs

Edit `export/main.js`, `window/main.js` or `rcy-sdk/src`, change `SPEC.md` or
`WINDOW.md` to match, then rebuild:

```
node rcy-sdk/bin/build.cjs
node rcy-sdk/dist/bundle.cjs export/main.js export/rcy-export
node rcy-sdk/dist/bundle.cjs window/main.js window/rcy-window
```

Both specifications pin the SDK build and its README by SHA-256, and
`python3 bin/check-sdk` reports a mismatch, so a change to the SDK also
updates those two hashes in each specification.

## Tests

```
cd rcy-sdk && node --test "test/*.test.ts"
```

The SDK tests need Node.js 23.6 or later.

```
NODE_PATH=tools/window-runtime/node_modules node features/window/scenarios.js \
    "$PWD/tools/window-runtime/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron" \
    "$PWD/window/rcy-window" "$PWD/export/rcy-export" "$PWD/presets/amen.wav"
```

The window scenarios open real windows and drive them with the pointer and
keyboard, so the machine's own pointer should stay still while they run.

The Gherkin scenarios for `rcy-export` run through `uv run bin/trial`. They
depend on `riemann-harness`, a private repository pinned in `pyproject.toml`,
and can't be installed without access to it.
