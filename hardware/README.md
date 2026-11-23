# rcy hardware tools

MIDI tools for samplers, as one Python package managed with `uv`. They are
independent of the kit programs in the repository root: they send WAV files
and parameters to a device, whatever produced the files.

| Device | Module | Documentation |
|---|---|---|
| Akai S2800, S3000, S3200 | `src/python/s2800` | `src/python/s2800/README.md`, `src/python/s2800/agent/README.md` |
| Akai MPC2000XL | `src/python/mpc2000xl` | `src/python/mpc2000xl/README.md` |
| Teenage Engineering EP-133 | `src/python/ep133` | `ep133-s2800-bridge.md` |
| MIDI ports and Sample Dump Standard | `src/python/midi` | `src/python/midi/README.md` |

## Commands

From the repository root, with `just`:

```
just s2800-agent param ZPLAY1      # look up a parameter in the SysEx specification, offline
just s2800-agent programs          # list the programs on a connected S2800
just s2800 upload kick.wav         # send a sample
just mpc upload kick.wav           # send a sample to an MPC2000XL
just controller 3                  # web controller for S2800 program 3
```

Without `just`, the same programs are `uv run --project hardware rcy-s2800-agent`,
`rcy-s2800` and `rcy-mpc`, or the wrappers in `hardware/tools/bin`.

Device access needs the `hardware` extra, which installs `python-rtmidi`:

```
uv sync --project hardware --extra hardware
```

## Tests

```
cd hardware && uv run --with pytest pytest -m s2800
```

Every test here needs its device connected, so a plain `pytest` run selects
none of them.
