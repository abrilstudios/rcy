# S2800 -- Akai S2800/S3000/S3200 Sampler Interface

Python interface for controlling the Akai S2800 (and compatible S3000/S3200) sampler over MIDI. Covers the full lifecycle: SysEx protocol encoding, device I/O, sample transfer, and a dedicated AI agent for protocol expertise.

## Why a dedicated agent?

The S2800 SysEx protocol is a 35-page specification covering 3 header types, 175+ parameters, 12 opcodes, nibble encoding, model-specific behavior, and non-obvious interactions between settings.

The parameter space is too large for any single agent to hold in context alongside other work. This is not just a human problem. An orchestrator agent like Claude Code running Opus has the same constraint: if you ask it to hold a 36-page SysEx spec in memory while also reasoning about Python code, managing git operations, editing files, and planning multi-step tasks, the orchestrator falls apart. Context gets diluted. The spec details blur. Hallucinations creep in on exact offsets, valid ranges, and model-specific behavior, precisely the details that matter most when constructing binary protocol messages.

The solution is the same principle that makes microservices work: **separate the specialist from the orchestrator.** The S2800 agent does one thing well. It holds the complete specification in its context window and nothing else. It does not manage files, plan refactors, or juggle unrelated tasks. Every token of its context is dedicated to the protocol. When Claude Code needs to diagnose voice stealing on a drum kit, it delegates to the specialist rather than trying to become one.

This separation has three concrete benefits:

1. **Defeat hallucination.** The specialist agent has the actual spec text and structured parameter data. It never guesses an offset or invents a range because the ground truth is right there in its context. The orchestrator never needs to hold protocol details at all.

2. **Scale the workflow.** The orchestrator stays fast and focused on coordination. The specialist handles deep protocol reasoning in parallel. Add more specialists (EP-133, S5000, MIDI SDS) and the orchestrator's context stays clean. Each specialist is independently testable and deployable.

3. **Accelerate iteration.** A user says "my drums are cutting each other off." Claude Code calls `s2800-agent summary` and `s2800-agent read-kg kgmute`, gets precise answers from the specialist, and acts on them. No context switching. No loading a 50KB spec into the main conversation. The specialist is always warm, always expert, always precise.

This is the agent design pattern: orchestrators coordinate, specialists execute. The alternative, one agent that tries to do everything, is how you get plausible-sounding SysEx messages with wrong byte offsets.

## Architecture

```
s2800/
  protocol.py    Pure functions: nibble encode/decode, message construction
  headers.py     Program/keygroup/sample header builders
  sampler.py     Device I/O: connect, read headers, write parameters, transfer samples
  connection.py  Shared connection singleton and batch read/write helpers
  sds.py         MIDI Sample Dump Standard for audio data transfer
  agent/         Dedicated AI agent for protocol expertise (see agent/README.md)
```

### Layer separation

Each module has a single responsibility and no upward dependencies:

- **protocol.py** -- Stateless encoding. Converts between Python values and SysEx byte sequences. No I/O, no device, no network. The foundation everything else builds on.
- **headers.py** -- Header construction. Builds valid 192-byte program, keygroup, and sample headers with correct defaults. Uses protocol.py for name encoding.
- **sampler.py** -- Device communication. Opens MIDI ports, sends/receives SysEx, handles retries and timeouts. The only module that touches hardware.
- **connection.py** -- Shared connection singleton and reusable I/O helpers (`read_kg_fields`, `write_kg_field`, `write_raw_bytes`). Keeps the agent tools and web controller DRY: both import from here instead of duplicating device access logic.
- **sds.py** -- Sample data transfer using the MIDI SDS standard. Packet framing, handshake protocol, 16-bit PCM packing.
- **agent/** -- Dedicated specialist that combines all of the above with the full specification text. Called by orchestrator agents; never calls them.

### Sampler class

`sampler.py` provides the `S2800` class, the single entry point for hardware interaction:

```python
from s2800 import S2800

s = S2800()
s.open()                          # Auto-detect MIDI ports
programs = s.list_programs()      # ['606 KIT', 'BASS 1', ...]
header = s.read_program_header(0) # 192 raw bytes
s.close()
```

It handles MIDI port detection (looks for "Volt" pattern on macOS), SysEx message framing, nibble encoding/decoding, and the S3K extended opcodes (0x27-0x2A) for partial read/write of individual parameters.

## Usage

The sampler module is used in three ways:

1. **From the CLI** (`tools/bin/s2800`) for direct device operations: upload samples, create programs, list contents.
2. **From orchestrator agents** via `just s2800-agent`, where the specialist reads and writes device state as part of a larger workflow the orchestrator is coordinating.
3. **From the web controller** (`just controller`) for real-time sound design -- see below.

Both CLI and agent paths go through the same `S2800` class. The agent adds domain expertise; the orchestrator adds workflow coordination. Neither tries to do the other's job.

## Web Controller

`tools/bin/909-controller.html` is a standalone TR-909-style browser GUI for real-time parameter editing. Open it with:

```bash
just controller          # program 3 (default)
just controller 1        # program 1
```

It opens directly in Chrome -- no web server or Python required. All communication goes through the browser's Web MIDI API via WebMIDI.js, talking to the S2800 over SysEx.

**Top section (blue knobs) -- program-level parameters:**

| Knob | Param | Range | Notes |
|------|-------|-------|-------|
| PAN | PANPOS | -50..+50 | Overall program pan |
| LOUD | PRLOUD | 0..99 | Overall loudness |
| STEREO | STEREO | 0..99 | Stereo spread |
| TUNE | PTUNO | -50..+50 | Program-wide pitch offset (semitones) |
| LFO RT | LFORAT | 0..99 | LFO1 rate (pitch/filter) |
| LFO DEP | LFODEP | 0..99 | LFO1 depth |
| PAN RT | PANRAT | 0..99 | LFO2 rate (pan) |
| PAN DEP | PANDEP | 0..99 | LFO2 depth |

**Bottom section (orange knobs) -- per-keygroup parameters (one column per drum voice):**

| Knob | Param | Range | Notes |
|------|-------|-------|-------|
| TUNE | KGTUNO | -50..+50 | Semitone transpose (stored as cents internally) |
| LEVEL | VLOUD1 | -50..+50 | Velocity zone loudness offset |
| PAN | VPANO1 | -50..+50 | Velocity zone pan offset |
| ATTACK | ATTAK1 | 0..99 | Amplitude envelope attack |
| DECAY | DECAY1 | 0..99 | Amplitude envelope decay |
| SUSTN | SUSTN1 | 0..99 | Sustain level -- **set to 0 for DECAY to be audible** |
| RELSE | RELSE1 | 0..99 | Release rate |
| FILTER | FILFRQ | 0..99 | Lowpass filter cutoff |

**Pad buttons** (bottom of each column) send MIDI Note On via channel 10 for instant audition while tweaking.

**Double-click** any knob to reset it to its center/default value.

### Amplitude envelope note

`build_keygroup()` defaults to `SUSTN1 = 99` (full sustain). This makes DECAY inaudible: the envelope decays from peak to 99, which is no change. For drum machine behavior where DECAY controls the length of the hit, set SUSTN to 0 on each voice. Then DECAY controls how quickly the sound fades from peak to silence.
