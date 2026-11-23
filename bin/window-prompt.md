You are generating one program from a specification: a desktop window for
slicing drum breaks, run by Electron. Work only in the current directory.

Read, in this order:

1. `WINDOW.md`, the complete behaviour of the window. Every sentence with
   "must", every table row and every formula is binding.
2. `rcy-sdk/README.md`, the functions that read WAV files and write the
   manifest. Don't read `rcy-sdk/dist/rcy-sdk.js` to learn a format; the
   README is the interface.

Write the program to `output/main.js`, then build `output/rcy-window` from it:

```
node rcy-sdk/dist/bundle.cjs output/main.js output/rcy-window
```

- `output/rcy-window` is the whole application in one file. Electron runs it
  as its main script, and the page (HTML, CSS, script) is inside it; it reads
  no other file of its own at run time and loads nothing from the network;
- `output/main.js` wraps its body in one function whose first statement is
  `"use strict";`. It is CommonJS source with no `#!` line. It uses the SDK
  through the constant `rcySdk`, which the bundle defines above it, and loads
  only Electron's and Node's built-in modules. The SDK exists in the main
  process only; the page gets what it needs from the main process;
- `output/rcy-window` is only ever written by that command. Run it again
  after every edit to `output/main.js`, and test `output/rcy-window`, not
  `output/main.js`;
- every constant in WINDOW.md's Constants table is defined once, by the name
  the table gives it, with a comment stating its unit and reason.

## Running and testing the window

Two environment variables are set for you. `$RCY_ELECTRON` is the Electron
binary (version 33), and `NODE_PATH` makes `require("playwright-core")` work
in any script you run with `node`. You are inside a process sandbox in which
Chromium's own sandbox can't start, so every launch needs `--no-sandbox`
before the program's path:

```
"$RCY_ELECTRON" --no-sandbox output/rcy-window --manifest FILE
```

```js
const { _electron } = require("playwright-core");
const app = await _electron.launch({
  executablePath: process.env.RCY_ELECTRON,
  args: ["--no-sandbox", "output/rcy-window", "--manifest", file],
});
const page = await app.firstWindow();
```

Drive the window with `page.mouse` and `page.keyboard`, read
`rcyWindowState()` with `page.evaluate`, and look at your work:
`page.screenshot({ path })` writes a PNG you can open with the Read tool.
Look at screenshots of the whole file, of a middle zoom and of the narrowest
view, and keep improving the drawing until a person could place a cut on a
zero crossing with it. An action that makes the program exit may reject in
Playwright because the page is gone; catch that. Every launch opens a real
window on the screen, so close each one, wait for its process to end, and
never leave one running. A test that hangs must be killed by a timer of your
own.

Synthesise your own test material under `output/`: WAV files through
`rcySdk.encodeWav` and manifests through `rcySdk.manifestText`, including
drum-like hits (short decaying bursts, some close together, some over a
noise floor) for Split by Transients. Check each numbered requirement and
each row of the tables through real pointer and key events.

You have no access to the acceptance scenarios; WINDOW.md is the only
statement of what they check. They drive the window exactly as described
above, without `--no-sandbox`. Beyond those checks the window is judged by a
person using it: how readable the waveform is at every zoom level, how
directly a cut can be placed, and how quickly the window responds. Where
WINDOW.md leaves appearance open, that is yours to design well. The detection
method of W12 is yours too; make it good on real drum breaks, not only on the
conditions W12 lists.

Don't read any file outside the current directory and don't modify any file
outside `output/`. Don't install anything.

Where WINDOW.md is silent or contradicts itself, don't guess silently: choose
the reading closest to the surrounding text and record it as a comment line
starting `// SPEC-GAP:` at the point in the code where the choice is made.

When the program is finished, write `output/build-manifest.json`:

```json
{
  "contract": "rcy-window/spec-v1",
  "spec_sha256": "<SHA-256 of WINDOW.md, lowercase hex>",
  "artifact_sha256": "<SHA-256 of output/rcy-window, lowercase hex>"
}
```

Compute both digests from the files' bytes after the last bundle run. Then stop.
