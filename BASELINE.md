# Reference implementation baseline

The corpus runs against the hand-written `rcy-export` in the `rcy` repository
as an unbound candidate:

```
uv run bin/trial --unbound --out reports/baseline \
  --interpreter /abs/path/to/node \
  --command '["/abs/path/to/rcy/.venv/bin/rcy-export"]'
```

Scenarios tagged `@baseline_red` state behaviour SPEC.md requires and the
reference implementation doesn't have. Every other scenario must pass against
it; a failure there means SPEC.md or the scenario misdescribes behaviour that
was meant to be kept. `-m "not baseline_red"` selects that set.

| Scenario | Requirement | Reference behaviour | Specified behaviour |
|---|---|---|---|
| boundaries-are-exact-integer-floors | R08 | Boundaries come from floating-point seconds, which lands one frame short where `i * N / n` is an exact integer. For 51999 frames in 7 slices the last boundary is 51998 and the final frame of the source is dropped. | `floor(i * N / n)` in integers. |
| nothing-is-written-outside-the-output-directory, a-refusal-writes-nothing | R04 | Writes `logs/rcy.log` under the current directory on every run. | Writes nothing outside the output directory. |
| input-refusal-for-unreadable-or-unsupported-audio (junk.wav) | R05 | Uncaught exception, traceback, exit code 1. | `cannot read audio file`, exit code 2. |
| same (w24.wav) | R05 | Accepts 24-bit input and writes 16-bit slices, requantising without a stated rule. | Refuses anything but 16-bit PCM. |
| same (ch3.wav) | R05 | Accepts three channels and writes a kit from the first two. | Refuses more than two channels. |
| same (tiny.wav) | R09 | Uncaught `ManifestError`, exit code 1. | `cannot cut 3 frames into 4 slices`, exit code 2. |
| same (69 slices, 200 slices of 3 frames) | R09 | Uncaught `ManifestError`, exit code 1. | The same message as a refusal, exit code 2. |
| catalog-directory-comes-from-the-environment, preset-without-a-catalog-variable, preset-catalog-file-missing, preset-entry-without-measures | R10, R11 | Presets come from a catalog inside the installed package; `RCY_PRESETS` is not read. | The catalog directory is named by `RCY_PRESETS` and its absence is a refusal. |
| manifest-refusals-the-reference-reports-differently (invalid JSON) | R22 | Appends the JSON parser's own message, which differs by parser. | `<path>: invalid JSON`. |
| same (missing source) | R22 | Uncaught exception, exit code 1. | `source audio not found`, exit code 2. |
| same (negative region start) | R22 | Message prints a Python tuple. | `region start must be >= 0, got -5`. |
| same (empty.wav) | R05 | Uncaught exception, exit code 1. | A source with no frames is `cannot read audio file`. |
| same (ext.wav) | R05 | Accepts a WAVE_FORMAT_EXTENSIBLE header. | Refuses any format tag but 1, so the program's own header check decides. |
| same (w24ch3.wav) | R05 | Accepts the file. | The width refusal, which is checked before the channel count. |
| same (`--input 001.wav --out .`) | R09 | Overwrites the source with its own first slice. | `would overwrite the source`. |
| same (`--out in.wav`) | R23 | Uncaught exception, exit code 1. | `output path is not a directory`, exit code 2. |
| midi-ticks-sit-on-the-grid-for-a-long-source, midi-ticks-round-to-the-nearest-tick | R15 | Note ticks are a floor of floating-point beats, and a note's end is its start plus a floored length. For 1817184 frames as 32 slices the second note starts on tick 239 and the third on 479, where the sixteenth-note grid is 240 and 480. | Nearest tick, in exact rational arithmetic; a note ends on the tick where the next begins. |
| manifest-refusal-for-types-names-and-tempo (`true`, string values) | R22 | Prints the value as Python does (`True`, `'x'`) or accepts it. | Prints the value as compact JSON; `true` is not an integer. |
| same (`a/b.wav`, `..`, `kit2.sfz`) | R22 | Writes the slice wherever the name points, including outside the output directory or over a kit file. | Refuses a name that is not a bare file name or that collides with a kit file. |
| same (bpm 3, bpm 70000000) | R15 | Doesn't refuse. | `tempo <bpm> BPM cannot be written to MIDI`. |
| a-slice-file-cannot-replace-the-source | R22 | Overwrites the source while reading from it. | `would overwrite the source`. |
| preset-catalog-unreadable-or-audio-missing | R11 | No catalog directory to be unreadable. | Named refusals for a broken catalog and a missing audio file. |
| every scenario in `exs.feature` | R24 | No `--exs` option; the argument is a syntax error. | Writes `<stem>.exs`, or refuses when a name doesn't fit the instrument format. |
