"""MIDI Sample Dump Standard (SDS) implementation.

Protocol-agnostic SDS encoding and packet building, shared with any
SDS-compatible sampler. Extracted from s5000/sds.py.

SDS message format:
    Header:  F0 7E [ch] 01 [num_lo] [num_hi] [format] [period...] [length...] [loop_start...] [loop_end...] [loop_type] F7
    Packet:  F0 7E [ch] 02 [packet_count] [120 bytes data] [checksum] F7
    ACK:     F0 7E [ch] 7F [packet_count] F7
    NAK:     F0 7E [ch] 7E [packet_count] F7
    CANCEL:  F0 7E [ch] 7D [packet_count] F7
    WAIT:    F0 7E [ch] 7C [packet_count] F7
"""

import time

# SDS constants
SDS_SYSEX_ID = 0x7E
SDS_DUMP_HEADER = 0x01
SDS_DATA_PACKET = 0x02
SDS_DUMP_REQUEST = 0x03
SDS_ACK = 0x7F
SDS_NAK = 0x7E
SDS_CANCEL = 0x7D
SDS_WAIT = 0x7C

# Packet data size
SDS_PACKET_DATA_BYTES = 120

# Timeouts
SDS_HANDSHAKE_TIMEOUT = 5.0
SDS_PACKET_TIMEOUT = 2.0

# Retries
SDS_MAX_RETRIES = 3


def pack_16bit_to_sds(pcm_bytes: bytes) -> bytes:
    """Pack 16-bit PCM samples into SDS 7-bit data format.

    SDS transmits each 16-bit sample as 3 bytes (ceil(16/7) = 3), MSB first:
        byte0: bits 15-9
        byte1: bits 8-2
        byte2: bits 1-0 shifted to bits 6-5

    Args:
        pcm_bytes: Raw 16-bit signed PCM bytes (little-endian)

    Returns:
        SDS 7-bit encoded sample data (3 bytes per sample)
    """
    result = bytearray()
    for i in range(0, len(pcm_bytes), 2):
        if i + 1 >= len(pcm_bytes):
            break
        sample = int.from_bytes(pcm_bytes[i:i + 2], 'little', signed=True)
        usample = sample & 0xFFFF
        result.append((usample >> 9) & 0x7F)
        result.append((usample >> 2) & 0x7F)
        result.append((usample << 5) & 0x7F)
    return bytes(result)


def unpack_sds_to_16bit(sds_data: bytes) -> bytes:
    """Unpack SDS 7-bit data back to 16-bit PCM samples.

    Args:
        sds_data: SDS-encoded sample data (3 bytes per sample)

    Returns:
        Raw 16-bit signed PCM bytes (little-endian)
    """
    result = bytearray()
    for i in range(0, len(sds_data), 3):
        if i + 2 >= len(sds_data):
            break
        b0 = sds_data[i] & 0x7F
        b1 = sds_data[i + 1] & 0x7F
        b2 = sds_data[i + 2] & 0x7F
        usample = (b0 << 9) | (b1 << 2) | (b2 >> 5)
        sample = usample if usample < 0x8000 else usample - 0x10000
        result.extend(sample.to_bytes(2, 'little', signed=True))
    return bytes(result)


def build_data_packet(packet_number: int, sample_data_7bit: bytes,
                      channel: int = 0x00) -> bytes:
    """Build an SDS Data Packet message.

    Args:
        packet_number: Running counter (0-127, wraps)
        sample_data_7bit: Already 7-bit encoded data (max 120 bytes)
        channel: SDS channel

    Returns:
        Complete SDS Data Packet SysEx message (127 bytes)
    """
    padded = bytearray(sample_data_7bit[:SDS_PACKET_DATA_BYTES])
    while len(padded) < SDS_PACKET_DATA_BYTES:
        padded.append(0x00)

    checksum = SDS_SYSEX_ID ^ (channel & 0x7F) ^ SDS_DATA_PACKET ^ (packet_number & 0x7F)
    for b in padded:
        checksum ^= b

    msg = bytearray([
        0xF0,
        SDS_SYSEX_ID,
        channel & 0x7F,
        SDS_DATA_PACKET,
        packet_number & 0x7F,
    ])
    msg.extend(padded)
    msg.append(checksum & 0x7F)
    msg.append(0xF7)
    return bytes(msg)


def parse_handshake(data: bytes) -> dict | None:
    """Parse an SDS handshake message (ACK/NAK/WAIT/CANCEL).

    Args:
        data: Raw SysEx bytes including F0/F7

    Returns:
        Dict with type, type_name, channel, packet_number; or None
    """
    if len(data) < 6:
        return None
    if data[0] != 0xF0 or data[1] != SDS_SYSEX_ID:
        return None

    msg_type = data[3]
    if msg_type not in (SDS_ACK, SDS_NAK, SDS_CANCEL, SDS_WAIT):
        return None

    type_names = {
        SDS_ACK: "ACK",
        SDS_NAK: "NAK",
        SDS_CANCEL: "CANCEL",
        SDS_WAIT: "WAIT",
    }

    return {
        "type": msg_type,
        "type_name": type_names[msg_type],
        "channel": data[2],
        "packet_number": data[4] & 0x7F,
    }


def wait_for_handshake(port_in, timeout: float = SDS_PACKET_TIMEOUT) -> dict | None:
    """Wait for an SDS handshake message from the receiver.

    Args:
        port_in: mido input port
        timeout: Maximum wait time in seconds

    Returns:
        Parsed handshake dict, or None on timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        for msg in port_in.iter_pending():
            if msg.type == 'sysex':
                raw = bytes([0xF0] + list(msg.data) + [0xF7])
                hs = parse_handshake(raw)
                if hs:
                    return hs
        time.sleep(0.01)
    return None
