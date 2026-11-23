# EP-133 ↔ S2800 MIDI Bridge Reference

## Octave Naming Convention Differences

Different devices use different octave numbering systems. **The MIDI note numbers are universal** - only the letter names differ.

| MIDI Note | EP-133 Display | S2800 / Scientific | Actual Pitch |
|-----------|----------------|-------------------|--------------|
| 24        | C1             | C1                | ~32.7 Hz     |
| 36        | C2             | C2                | ~65.4 Hz     |
| 48        | C3             | C3                | ~130.8 Hz    |
| 60        | C4             | C4 (Middle C)     | ~261.6 Hz    |
| 72        | C5             | C5                | ~523.3 Hz    |

**Key difference:** EP-133 uses Yamaha/Roland convention, same as S2800 in this range.

---

## EP-133 Group MIDI Note Ranges

Each EP-133 group has 12 pads that send fixed MIDI notes:

| Group | MIDI Notes | EP-133 Display | Note Names        |
|-------|------------|----------------|-------------------|
| A     | 36-47      | C2-B2          | C2, C#2...B2      |
| B     | 48-59      | C3-B3          | C3, C#3...B3      |
| C     | 60-71      | C4-B4          | C4, C#4...B4      |
| D     | 72-83      | C5-B5          | C5, C#5...B5      |

**Note:** These MIDI note outputs are **hardwired** per group and cannot be changed via SysEx.

---

## Current Configuration (2026-02-15)

### S2800 "606 KIT" Program (Slot 2)
- **MIDI Channel:** 10
- **Keygroups:** 4 mapped sounds

| MIDI Note | Note Name | Sample  | Description       |
|-----------|-----------|---------|-------------------|
| 36        | C2        | KICK    | Bass Drum         |
| 38        | D2        | SNARE   | Snare             |
| 42        | F#2       | CL HAT  | Closed Hi-Hat     |
| 46        | A#2       | OP HAT  | Open Hi-Hat       |

### EP-133 Group D Configuration
- **MIDI Channel:** 10 (configured via metadata)
- **MIDI Notes Sent:** 72-83 (C5-B5)
- **Pads:** 12 physical pads

### The Problem
EP-133 Group D (notes 72-83) and S2800 606 KIT (notes 36, 38, 42, 46) **do not overlap**.
- Group D sends notes that are 3 octaves higher than the S2800 listens for
- To trigger S2800 from EP-133, use **Group A** (notes 36-47) instead

### Solution Options
1. **Use EP-133 Group A** - it sends notes 36-47, which overlaps with S2800's 36, 38, 42, 46
2. **Upload 606 samples to EP-133** - use them internally, no MIDI needed
3. **Reconfigure S2800 606 KIT** - map keygroups to notes 72-83 to match Group D

---

## EP-133 MIDI Channel Configuration

Each pad can be configured to send on a specific MIDI channel via metadata:

```python
from ep133 import EP133Device

with EP133Device() as ep:
    # Group D pad 1 is node_id 3501
    # Set to MIDI channel 10 (protocol value = 9)
    meta = ep.get_metadata(3501)
    meta['midi.channel'] = 9  # Channel 10 (1-indexed)
    ep.set_metadata(3501, meta)
```

**Current State:** All Group D pads (3501-3512) configured to send on channel 10.

---

## S2800 Program Reading

Use the `s2800-agent` tool to inspect current mappings:

```bash
# List all programs
tools/bin/s2800-agent programs

# Get full program summary
tools/bin/s2800-agent summary 2

# Read specific keygroup parameters
tools/bin/s2800-agent read-kg LONOTE 2 0  # Program 2, Keygroup 0, low note
tools/bin/s2800-agent read-kg SNAME1 2 0  # Sample name for keygroup 0
```

---

## General MIDI (GM) Drum Map Reference

Standard GM drum notes (used by S2800 606 KIT):

| MIDI Note | Note Name | GM Drum Sound      |
|-----------|-----------|--------------------|
| 35        | B1        | Acoustic Bass Drum |
| 36        | C2        | Bass Drum 1        |
| 38        | D2        | Acoustic Snare     |
| 42        | F#2       | Closed Hi-Hat      |
| 44        | G#2       | Pedal Hi-Hat       |
| 46        | A#2       | Open Hi-Hat        |
| 48        | C3        | Hi Mid Tom         |
| 50        | D3        | High Tom           |

**GM Drums Channel:** Always channel 10 (MIDI channel 9 in protocol).
