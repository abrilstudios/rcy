# rcy

rcy cuts a drum break into a sampler kit, and it is built to be run by an
agent. The agent decides which break, how many pads and where the files go,
then starts a program with all of that on the command line. A person is
brought in for the one step that needs ears, placing the cuts, in a window
that opens already set up for the task and closes when they save.

There are two programs. `rcy-export` writes kits and never asks anything.
`rcy-window` is the window.

This is an alpha; the file formats and command lines can still change.

## The contract

A window run is a function call with a person inside it.

| | |
|---|---|
| In | A manifest, the opening split, the task text, and optionally the slice count the result must have. All of it is on the command line. |
| Out | An exit code, the edited manifest at `--out`, and a run record at `--record`. |

| Exit code | Meaning | What the caller does |
|---|---|---|
| 0 | The person saved. | Cut the kit from the manifest at `--out`. |
| 3 | The person closed without saving. | Nothing was written to `--out`; stop or ask again. |
| 2 | The launch was refused; the reason is on stderr. | Fix the command line. |

The window has no file picker, no save-as dialog and no setup screen, because
everything they would ask is already in the arguments.

## Scripted workflows

Each script in `workflows/` is one whole task: it prepares the manifest,
opens the window, waits, and acts on the exit code. They are plain `sh` and
short enough to read before running.

Every workflow takes a new task directory and leaves this in it:

```
TASK_DIR/
  source/            the break as one slice per measure, and its manifest
  edited.rcy.json    the manifest the person saved
  run.json           the run record
  <name>/            the kit: WAV slices, .sfz, .exs, .mid, .rcy.json
```

A workflow exits with the window's code, so the caller reads one number.

### Cut a new kit

```
workflows/new-kit presets/amen.wav 4 work/amen
```

The arguments are the source, its length in 4/4 measures, and the task
directory. The window opens with the break split into eighth notes and the
task written across the top:

![The window as new-kit opens it: 32 cuts on an eighth-note grid and the task text](docs/screenshots/new-kit-opening.png)

The person clicks a slice to hear it, drags a cut onto its hit, and
double-clicks to add or remove one. The wheel, or `=` and `-`, zooms as far
as single frames:

![Zoomed in on one cut while it is dragged](docs/screenshots/moving-a-cut.png)

Save ends the run. The script then cuts the kit from the saved manifest with
20 ms of source audio kept either side of each slice (see the buffer below).

### Cut exactly N pads

```
workflows/pick-hits presets/amen.wav 4 5 work/five
```

The third argument is the number of slices the result must have. The window
opens with cuts at detected transients, and Save stays unavailable while the
count is wrong:

![pick-hits at opening: 8 slices, 5 asked, Save unavailable](docs/screenshots/pick-hits-count-unmet.png)

Once the count matches, Save becomes available:

![pick-hits with 5 slices: Save available](docs/screenshots/pick-hits-count-met.png)

An agent that needs five pads for a five-pad program therefore never receives
a kit of four or six.

### Correct an existing kit

```
workflows/recut work/amen/amen/amen.rcy.json work/amen-2
```

The window opens on the kit's own cuts, unchanged, and the script cuts a new
kit from whatever is saved.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `RCY_BUFFER_MS` | 20 | Milliseconds of source audio kept either side of each slice. |
| `RCY_SPLIT_RESOLUTION` | 8 | `new-kit`: slices per measure in the opening split. |
| `RCY_SENSITIVITY` | 50 | `pick-hits`: transient sensitivity of the opening split, 0 to 99. |
| `RCY_ELECTRON` | the binary under `tools/window-runtime` | The Electron binary that runs the window. |

## The run record

Every run writes the file named by `--record`, whether the person saved or
not. Its shape, shortened:

```json
{
  "rcy_window_run": 1,
  "arguments": ["--manifest", ".../source.rcy.json", "--split", "transients", "--expect-slices", "5", "..."],
  "started_at": "...", "ended_at": "...", "duration_ms": 1785,
  "exit_code": 0,
  "outcome": "saved",
  "opening": { "boundaries": [0, 19608, 48539, 87271, 145469, 183914, 221429, 231492, 307411] },
  "events": [
    { "t_ms": 662, "kind": "edit", "what": "Cut at frame 19608 removed", "slices": 7 },
    { "t_ms": 1210, "kind": "play", "from": 0, "to": 9606 }
  ],
  "final": { "boundaries": [0, 145469, 183914, 221429, 231492, 307411] }
}
```

`opening` is what the agent proposed and `final` is what the person kept;
`events` holds each edit, undo, redo and audition between them with its time
in milliseconds. Comparing the two across many records shows where the
first-pass split is wrong, which is why the records are meant to be kept.
They name local paths, so `runs/` is ignored by git.

## Writing a different task

A workflow is a few lines around one launch. To state a different task, call
the window directly:

```
electron window/rcy-window --manifest KIT.rcy.json --out EDITED.rcy.json --record RUN.json \
    [--split measures --resolution R | --split transients --sensitivity S] \
    [--view START:END] [--select I] [--task TEXT] [--expect-slices K]
```

`electron` here is the binary at
`tools/window-runtime/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron`.
`--view` opens zoomed to a frame range and `--select` opens with one slice
selected, so a task can point the person at the one cut in question.
`WINDOW.md` states every option, key and refusal.

## Kits

`rcy-export` writes one directory:

| File | Contents |
|---|---|
| `001.wav`, `002.wav`, ... | One WAV per slice, copied from the source without resampling, fades or gain change. |
| `<name>.sfz` | An SFZ instrument, one region per slice from MIDI key 60 upward. |
| `<name>.exs` | With `--exs`, a Logic Pro Sampler instrument. |
| `<name>.mid` | A MIDI file that plays the slices in order at the break's tempo. |
| `<name>.rcy.json` | The manifest: source, tempo, cut positions in frames, and each slice's key and file. |

```
node export/rcy-export --input break.wav --measures 2 --resolution 8 --out /tmp/kit
node export/rcy-export --from-manifest /tmp/kit/kit.rcy.json --out /tmp/kit2 --exs --buffer-ms 20
RCY_PRESETS=presets node export/rcy-export --preset amen_classic --out /tmp/amen
```

The manifest is the editable form of a kit: the window reads and writes it,
and `--from-manifest` cuts the kit again from it. Sources are 16-bit WAV at
44.1 kHz, mono or stereo. Tempo comes from the length of the break and its
measure count, and nothing is time-stretched.

`--buffer-ms N` keeps N milliseconds of source audio either side of each
slice in its file and writes the slice's start and end points into the SFZ
and EXS instruments. A cut placed a few milliseconds into a hit then loses
nothing, and the points stay adjustable in the sampler. Without the option a
file holds exactly its slice.

`SPEC.md` states every option, file format rule and refusal message.

## Install

```
git clone https://github.com/abrilstudios/rcy && cd rcy
npm ci --prefix tools/window-runtime
```

`rcy-export` needs only Node.js; versions 24 and 26 are the ones it has run
on. The second command installs Electron 33 for the window, which is built
and tested on macOS.

## Layout

| Path | Contents |
|---|---|
| `workflows/` | The scripted tasks above. |
| `SPEC.md`, `WINDOW.md` | The behaviour of the two programs, kept in step with the code. |
| `export/main.js`, `window/main.js` | The programs' sources. |
| `export/rcy-export`, `window/rcy-window` | The programs as run: each is the SDK followed by its source, in one file. |
| `rcy-sdk/` | The code for every file format (WAV, MIDI, SFZ, EXS, manifest), with its tests and `dist/bundle.cjs`, which builds a program file. |
| `presets/` | The preset catalog and its audio. |
| `features/` | Acceptance scenarios: Gherkin for `rcy-export`, a Playwright script for the window. |
| `docs/screenshots/` | The pictures in this file and `capture.js`, which takes them from the running window. |
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

After a change to how the window looks, retake the screenshots:

```
NODE_PATH=tools/window-runtime/node_modules node docs/screenshots/capture.js \
    "$PWD/tools/window-runtime/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron"
```

## Tests

```
cd rcy-sdk && node --test "test/*.test.ts"
```

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
