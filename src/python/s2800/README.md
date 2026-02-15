# S2800 -- Akai S2800/S3000/S3200 Sampler Interface

Python interface for controlling the Akai S2800 (and compatible S3000/S3200) sampler over MIDI. Covers the full lifecycle: SysEx protocol encoding, device I/O, sample transfer, and an AI agent that can reason about the protocol and operate the hardware.

## Why an agent?

The S2800 SysEx protocol is a 35-page specification covering 3 header types, 175+ parameters, 12 opcodes, nibble encoding, model-specific behavior, and non-obvious interactions between settings. Traditional approaches to this problem (lookup tables, CLI flags, man pages) fail because:

1. **The protocol requires reasoning, not just lookup.** Fixing voice stealing on a drum kit requires understanding that mute groups, polyphony, voice assignment, and priority all interact. A lookup table tells you KGMUTE is at offset 160; it does not tell you that your hi-hat should be in mute group 1 while your kick should be OFF.

2. **The parameter space is too large for a human to hold in context.** A single program has 60 parameters. Each keygroup adds 85 more. A 4-keygroup drum kit has 400+ parameters that could be causing a problem. The agent can read all of them, cross-reference against the spec, and narrow the diagnosis.

3. **Device state matters as much as protocol knowledge.** Knowing the SysEx format is necessary but not sufficient. The agent connects to the hardware, reads actual values, compares them against the spec, and writes corrections -- closing the loop between documentation and reality.

The agent pattern (LLM + tools + domain context) is the right fit because it combines fuzzy reasoning ("my drums are cutting each other off") with precise execution (read KGMUTE from all 4 keygroups, identify the conflict, write the fix).

## Architecture

```
s2800/
  protocol.py    Pure functions: nibble encode/decode, message construction
  headers.py     Program/keygroup/sample header builders
  sampler.py     Device I/O: connect, read headers, write parameters, transfer samples
  sds.py         MIDI Sample Dump Standard for audio data transfer
  agent/         AI agent that reasons over the protocol (see agent/README.md)
```

### Layer separation

Each module has a single responsibility and no upward dependencies:

- **protocol.py** -- Stateless encoding. Converts between Python values and SysEx byte sequences. No I/O, no device, no network. The foundation everything else builds on.
- **headers.py** -- Header construction. Builds valid 192-byte program, keygroup, and sample headers with correct defaults. Uses protocol.py for name encoding.
- **sampler.py** -- Device communication. Opens MIDI ports, sends/receives SysEx, handles retries and timeouts. The only module that touches hardware.
- **sds.py** -- Sample data transfer using the MIDI SDS standard. Packet framing, handshake protocol, 16-bit PCM packing.
- **agent/** -- AI layer that combines all of the above with the full specification text to reason about protocol questions and operate the device.

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

The sampler module is used in two ways:

1. **From the CLI** (`tools/bin/s2800`) for direct device operations: upload samples, create programs, list contents.
2. **From the agent** (`tools/bin/s2800-agent`) where the AI reads and writes device state as part of reasoning about protocol questions.

Both paths go through the same `S2800` class; the agent just adds a reasoning layer on top.
