# MIDI -- Shared MIDI Utilities

Shared MIDI utilities used by both `s2800/` and `mpc2000xl/`. Covers port detection and the MIDI Sample Dump Standard (SDS) protocol.

## Architecture

```
midi/
  ports.py    Port detection by name pattern
  sds.py      MIDI Sample Dump Standard protocol
```

---

## ports.py

`find_ports(patterns)` searches available MIDI ports by name substring, returning the first match for input and output.

```python
from midi.ports import find_ports

in_port, out_port = find_ports(["MPC", "Volt 2", "Volt"])
```

Each device class passes its own priority list:

| Device | Patterns |
|--------|----------|
| S2800 | `["S2800", "Akai", "Volt 2", "Volt"]` |
| MPC2000XL | `["MPC", "Volt 2", "Volt"]` |

---

## sds.py -- MIDI Sample Dump Standard

Implementation of the [MIDI Sample Dump Standard (MMA)](https://www.midi.org/specifications/midi1-specifications/midi-sample-dump-standard) for transferring audio to hardware samplers.

### Protocol overview

```
Host -> Device:  SDS Dump Header  (F0 7E ch 01 ...)
Device -> Host:  ACK              (F0 7E ch 7F ...)
Host -> Device:  SDS Data Packet  (F0 7E ch 02 ...)  x N
Device -> Host:  ACK per packet
```

### Encoding

SDS transmits 16-bit samples as three 7-bit MIDI bytes (21 bits total, MSB first, left-justified):

```
byte0 = bits 15-9
byte1 = bits  8-2
byte2 = bits  1-0 (in bits 6-5)
```

**Offset binary.** SDS uses unsigned offset binary, NOT signed two's complement:

| Value | Two's complement | Offset binary (SDS) |
|-------|-----------------|---------------------|
| Silence | 0x0000 | 0x8000 |
| Max positive | 0x7FFF | 0xFFFF |
| Max negative | 0x8000 | 0x0000 |

Conversion: `usample = (sample & 0xFFFF) ^ 0x8000`

Without this conversion samples arrive inverted and heavily distorted.

### Functions

```python
from midi.sds import (
    pack_16bit_to_sds,    # encode 16-bit PCM -> SDS 7-bit
    unpack_sds_to_16bit,  # decode SDS 7-bit -> 16-bit PCM
    build_data_packet,    # build SDS Data Packet SysEx
    parse_handshake,      # parse ACK/NAK/WAIT/CANCEL
    wait_for_handshake,   # wait for handshake with timeout
)
```

### Constants

```python
SDS_ACK = 0x7F
SDS_NAK = 0x7E
SDS_CANCEL = 0x7D
SDS_WAIT = 0x7C
SDS_HANDSHAKE_TIMEOUT = 5.0   # seconds (for initial ACK after header)
SDS_PACKET_TIMEOUT = 2.0      # seconds (between packets)
SDS_MAX_RETRIES = 3
SDS_PACKET_DATA_BYTES = 120   # 7-bit bytes of sample data per packet
```

### Packets and sample counts

Each SDS data packet carries 120 bytes of 7-bit data. Each 16-bit sample encodes to 3 bytes, so each packet holds 40 samples:

```
packets = ceil(num_samples * 3 / 120)
```
