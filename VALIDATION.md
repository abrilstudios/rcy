# VALIDATION.md

How a candidate `rcy-export` is graded. This file is for whoever maintains the
scenarios and the harness; the generator never receives it.

**I1. Files are the oracle.** A candidate is graded by the files it wrote and
by its exit code and output lines, read by code the candidate did not write:
the standard library's `wave` and `json` modules and the harness's own MIDI
reader. A candidate's claim about what it wrote is never evidence; the
`slices: 8` line is checked as a line of text, and the eight files are counted
separately.

**I2. The harness knows file formats, not the product.** `harness/` records
facts such as a WAV's frame count, a line of a text file or a MIDI tick. It has
no function or event named after a slice, a tempo, a kit or a preset. A new
scenario should need a new docstring, not new harness code.

**I3. The trace is the only contract surface.** Every assertion is one of the
five generic operators (`contains`, `not_contains`, `order`, `count`,
`field_exists`) over `trace.jsonl`.

**I4. Every requirement has a scenario.** Each `R` identifier in SPEC.md is
tagged on at least one scenario, and `bin/check-coverage` fails otherwise. A
requirement added without a scenario is not enforced.

## Audit before promoting a candidate

- I1 to I3: `grep -rn "slice\|tempo\|preset\|kit" harness/*.py` matches only comments, docstrings and the MIDI tempo meta-event.
- I4: `bin/check-coverage` exits 0.
- I5: the artifact's SHA-256 equals `artifact_sha256` in `build-manifest.json`.
- I6: `bin/check-sdk ARTIFACT` passes, and the program after the SDK's end marker loads only `node:` built-in modules.
- I11: the program after the SDK's end marker holds no byte layout of a WAV, MIDI, SFZ, manifest or EXS file and calls the `rcySdk` function SPEC.md names for each.
- I7, I8, I9: read the artifact's argument handling, its WAV writing and its boundary arithmetic.
- I10: run one export twice into two directories and compare the files.
- R04: the harness can't see a temporary file written outside the trial's work directory; read the artifact for `os.tmpdir` and for paths outside the output directory.
- Path handling: the trial's work directory holds no symbolic links, so no scenario separates lexical path handling from resolved paths. Read the artifact against the "absolute path" term in SPEC.md.
