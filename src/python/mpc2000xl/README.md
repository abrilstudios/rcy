# MPC2000XL -- Akai MPC2000XL Interface

Python interface for transferring samples to the Akai MPC2000XL over MIDI using the MIDI Sample Dump Standard (SDS). Covers device connection, audio encoding, SDS handshaking, and break-slicing workflows.

## Architecture

```
mpc2000xl/
  device.py    Device I/O: connect, transfer samples, trigger pads
```

### Device class

`device.py` provides the `MPC2000XL` class, the single entry point for hardware interaction:

```python
from mpc2000xl import MPC2000XL

with MPC2000XL() as mpc:
    mpc.upload_sample(pcm_bytes, sample_rate=44100)
    mpc.trigger_pad(1)
    mpc.program_change(0)
```

Port detection searches for "MPC", "Volt 2", "Volt" in that order. On a Volt 2 interface the device is found automatically.

## Sample Transfer Protocol

The MPC2000XL uses standard MIDI SDS (not Akai-proprietary SysEx). Transfer flow:

1. Host sends **SDS Dump Header** (`F0 7E ch 01 ...`) with sample metadata
2. MPC sends **ACK** (`F0 7E ch 7F ...`)
3. Host sends **SDS Data Packets** (`F0 7E ch 02 ...`), 120 bytes each
4. MPC ACKs every packet
5. On completion the MPC stores the sample in RAM

See `src/python/midi/sds.py` for the shared SDS implementation.

### Preparing the MPC to receive

The MPC must be on the sample dump receive screen before each transfer:

```
SHIFT + MIDI/SYNC  ->  DUMP [F2]
```

Stay on that screen for the duration of the transfer. The screen shows "Receiving..." during transfer. Samples are stored sequentially in RAM regardless of the slot number in the SDS header.

### Key protocol findings

**Offset binary encoding.** SDS uses offset binary, not signed two's complement. Silence is `0x8000`, not `0x0000`. Without the XOR `0x8000` conversion the waveform arrives inverted and heavily distorted. The `pack_16bit_to_sds()` function in `midi/sds.py` handles this correctly.

**Slot number is ignored.** The MPC ignores the sample number field in the SDS Dump Header and assigns samples sequentially: first received = MIDI_1, second = MIDI_2, etc.

**No MIDI naming.** The MPC auto-names received samples MIDI_1, MIDI_2, etc. The SDS name extension (`F0 7E ch 05 01 ...`) is not supported. Renaming must be done manually on the device. There is no workaround.

**No program creation via MIDI.** The MPC2000XL's sampler section has no SysEx support at all (both TX and RX are marked X in the MIDI implementation chart). Program/pad assignment must be done on the device. Only the sequencer section supports SysEx (model ID `0x45`).

**Sequencer SysEx.** For MMC (transport control) and sequencer-section SysEx the model byte is `0x45` under Akai manufacturer `0x47`.

## Usage

### CLI

```bash
# List MIDI ports
just mpc ports

# Upload a single WAV
just mpc upload sounds/909/BD_909_Tape_Short_E_05.wav

# Upload all 16 slices of a break
for i in $(seq -f "%02g" 1 16); do
  just mpc upload exports/think_break_16/think_$i.wav
done
```

### Break slicing workflow

The standard workflow for loading a break onto the MPC:

```bash
# 1. Slice a source file into 16 equal 16th-note pieces
python -c "
import soundfile as sf, numpy as np, os

path = 'path/to/break.wav'          # must be N bars long
n_bars = 4                          # number of bars in the file
prefix = 'think'                    # output name prefix
outdir = 'exports/think_break_16'

y, sr = sf.read(path, dtype='float32')
if y.ndim > 1:
    y = y.mean(axis=1)

bar_frames = len(y) // n_bars
one_bar = y[:bar_frames]
slice_frames = bar_frames // 16

os.makedirs(outdir, exist_ok=True)
for i in range(16):
    slc = one_bar[i*slice_frames:(i+1)*slice_frames]
    sf.write(f'{outdir}/{prefix}_{i+1:02d}.wav', slc, sr)
"

# 2. Put MPC on SHIFT+MIDI/SYNC > DUMP [F2]

# 3. Upload all 16
for i in $(seq -f "%02g" 1 16); do
  just mpc upload exports/think_break_16/think_$i.wav
done

# 4. Rename on MPC: MIDI_1 -> THINK_01, MIDI_2 -> THINK_02, etc.
```

### Python API

```python
import soundfile as sf
from mpc2000xl import MPC2000XL

# Upload a WAV file
data, rate = sf.read('kick.wav', dtype='int16')
if data.ndim > 1:
    data = data[:, 0]   # mono

with MPC2000XL() as mpc:
    mpc.upload_sample(data.tobytes(), rate)

# Trigger pads (default GM drum map)
with MPC2000XL() as mpc:
    mpc.trigger_pad(1)           # pad 1 = note 36 (kick)
    mpc.trigger_pad(2)           # pad 2 = note 38 (snare)
    mpc.send_note(60, velocity=100, channel=0)

# Program change
with MPC2000XL() as mpc:
    mpc.program_change(0)
```

## MIDI Implementation Summary

| Feature | Supported | Notes |
|---|---|---|
| Sample transfer (SDS) | Yes | SHIFT+MIDI/SYNC > DUMP [F2] required |
| Sample naming via MIDI | No | Always MIDI_N, rename manually |
| Pad trigger (note on/off) | Yes | Standard MIDI, default GM map |
| Program change | Yes | Standard MIDI |
| MIDI CC | Yes | Limited params |
| Program creation via MIDI | No | Sampler section has no SysEx |
| Sequence dump/load | Yes | Sequencer SysEx, model ID 0x45 |
| MMC transport control | Yes | Sequencer SysEx |

## Default Pad Map

```python
DEFAULT_PAD_NOTES = {
    1: 36,   # Kick
    2: 38,   # Snare
    3: 42,   # Closed HH
    4: 46,   # Open HH
    5: 41,   # Low Floor Tom
    6: 43,   # High Floor Tom
    7: 45,   # Low Tom
    8: 47,   # Low-Mid Tom
    9: 48,   # Hi-Mid Tom
    10: 50,  # High Tom
    11: 39,  # Hand Clap
    12: 49,  # Crash
    13: 51,  # Ride
    14: 55,  # Splash / Ride Bell
    15: 54,  # Tambourine
    16: 56,  # Cowbell
}
```

Override at construction time:

```python
mpc = MPC2000XL(pad_notes={1: 60, 2: 62, ...})
```
