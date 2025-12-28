"""EP-133 SysEx protocol primitives.

This module provides low-level protocol encoding/decoding based on
reverse-engineering of the EP-133 Sample Tool.

Message format:
    F0 00 20 76 33 40 <cmd> <seq> [<sub>] [<7bit_payload>] F7

Commands (request/response pairs):
    0x69/0x29 - General file operations
    0x6a/0x2a - File operations (alternate)
    0x6b/0x2b - File operations (alternate)
    0x70/0x30 - Init/status
    0x40      - Status notifications (device->host only)
"""

# TE SysEx header bytes
TE_MANUFACTURER = bytes([0x00, 0x20, 0x76])
TE_DEVICE_ID = 0x33
TE_CHANNEL = 0x40

# TE_SYSEX_FILE sub-commands (byte after seq)
TE_SYSEX_FILE = 0x05
TE_SYSEX_FILE_INIT = 0x01
TE_SYSEX_FILE_PUT = 0x02
TE_SYSEX_FILE_GET = 0x03
TE_SYSEX_FILE_LIST = 0x04
TE_SYSEX_FILE_PLAYBACK = 0x05
TE_SYSEX_FILE_DELETE = 0x06
TE_SYSEX_FILE_METADATA = 0x07

# Metadata sub-operations
TE_SYSEX_FILE_METADATA_SET = 0x01
TE_SYSEX_FILE_METADATA_GET = 0x02


def pack_7bit(data: bytes) -> bytes:
    """Pack data using TE's 7-bit encoding.

    Every 7 bytes of input become 8 bytes of output:
    - First byte = MSB flags for the next 7 bytes
    - Next 7 bytes have their MSBs stripped

    Args:
        data: Raw bytes to encode

    Returns:
        7-bit encoded bytes safe for MIDI SysEx
    """
    result = bytearray()
    for i in range(0, len(data), 7):
        chunk = data[i:i+7]
        flags = 0
        encoded_bytes = []
        for j, b in enumerate(chunk):
            if b & 0x80:
                flags |= (1 << j)
            encoded_bytes.append(b & 0x7F)
        result.append(flags)
        result.extend(encoded_bytes)
    return bytes(result)


def unpack_7bit(data: bytes) -> bytes:
    """Unpack TE's 7-bit encoded data.

    Every 8 bytes of input become 7 bytes of output:
    - First byte contains MSB flags for next 7 bytes
    - Remaining bytes have MSBs restored from flags

    Args:
        data: 7-bit encoded bytes

    Returns:
        Decoded raw bytes
    """
    result = bytearray()
    i = 0
    while i < len(data):
        if i >= len(data):
            break
        flags = data[i]
        i += 1
        for bit in range(7):
            if i >= len(data):
                break
            msb = ((flags >> bit) & 1) << 7
            result.append((data[i] & 0x7F) | msb)
            i += 1
    return bytes(result)


def build_te_message(cmd: int, seq: int, payload: bytes = b"") -> bytes:
    """Build a complete TE SysEx message.

    Args:
        cmd: Command byte (e.g., 0x69, 0x6a)
        seq: Sequence number (0x00-0x7F)
        payload: Already 7-bit encoded payload (optional)

    Returns:
        Complete SysEx message including F0 and F7
    """
    msg = bytearray([0xF0])
    msg.extend(TE_MANUFACTURER)
    msg.append(TE_DEVICE_ID)
    msg.append(TE_CHANNEL)
    msg.append(cmd & 0x7F)
    msg.append(seq & 0x7F)
    msg.extend(payload)
    msg.append(0xF7)
    return bytes(msg)


def parse_te_response(data: bytes) -> dict | None:
    """Parse a TE SysEx response message.

    Args:
        data: Raw SysEx message bytes (including F0/F7)

    Returns:
        Dict with parsed fields, or None if not a valid TE message
    """
    # Minimum: F0 <mfr:3> <dev> <chan> <cmd> <seq> F7 = 9 bytes
    if len(data) < 9:
        return None

    if data[0] != 0xF0 or data[-1] != 0xF7:
        return None

    if data[1:4] != TE_MANUFACTURER:
        return None

    if data[4] != TE_DEVICE_ID:
        return None

    result = {
        "cmd": data[6],
        "seq": data[7],
        "is_response": (data[6] & 0xF0) == 0x20,
        "raw": data,
    }

    # For responses, byte 8 is sub-command, byte 9 is status
    if result["is_response"] and len(data) > 9:
        result["sub"] = data[8]
        if len(data) > 10:
            result["status"] = data[9]
            # Payload starts at byte 10, ends before F7
            encoded_payload = data[10:-1]
            if encoded_payload:
                result["payload"] = unpack_7bit(encoded_payload)

    return result


def build_file_list_request(seq: int, node_id: int, page: int = 0) -> bytes:
    """Build a FILE LIST request message.

    Args:
        seq: Sequence number
        node_id: Node ID of directory to list
        page: Page number (for pagination)

    Returns:
        Complete SysEx message
    """
    # Payload: [LIST, page_hi, page_lo, nodeId_hi, nodeId_lo]
    # Don't mask with 0x7F - pack_7bit handles MSBs
    payload_raw = bytes([
        TE_SYSEX_FILE_LIST,
        (page >> 8) & 0xFF,
        page & 0xFF,
        (node_id >> 8) & 0xFF,
        node_id & 0xFF,
    ])
    payload = pack_7bit(payload_raw)

    # Use command 0x6a (from capture analysis)
    full_payload = bytes([TE_SYSEX_FILE]) + payload
    return build_te_message(0x6a, seq, full_payload)


def build_metadata_get_request(seq: int, node_id: int, page: int = 0) -> bytes:
    """Build a METADATA GET request message.

    Args:
        seq: Sequence number
        node_id: Node ID to get metadata for
        page: Page number for paginated metadata (default 0)

    Returns:
        Complete SysEx message
    """
    payload_raw = bytes([
        TE_SYSEX_FILE_METADATA,
        TE_SYSEX_FILE_METADATA_GET,
        (node_id >> 8) & 0xFF,
        node_id & 0xFF,
        (page >> 8) & 0xFF,
        page & 0xFF,
    ])
    payload = pack_7bit(payload_raw)
    full_payload = bytes([TE_SYSEX_FILE]) + payload
    return build_te_message(0x6a, seq, full_payload)


def build_metadata_set_request(seq: int, node_id: int, metadata: str) -> bytes:
    """Build a METADATA SET request message.

    Args:
        seq: Sequence number
        node_id: Node ID to set metadata on
        metadata: JSON string to set

    Returns:
        Complete SysEx message
    """
    metadata_bytes = metadata.encode('utf-8') + b'\x00'
    payload_raw = bytes([
        TE_SYSEX_FILE_METADATA,
        TE_SYSEX_FILE_METADATA_SET,
        (node_id >> 8) & 0xFF,
        node_id & 0xFF,
    ]) + metadata_bytes
    payload = pack_7bit(payload_raw)
    full_payload = bytes([TE_SYSEX_FILE]) + payload
    return build_te_message(0x6a, seq, full_payload)


def build_file_init_request(seq: int) -> bytes:
    """Build a FILE INIT request message.

    This must be called before listing directories.

    Args:
        seq: Sequence number

    Returns:
        Complete SysEx message
    """
    # Payload from capture: 01 01 00 40 00 (unpacked)
    # 01 = INIT, 01 = ?, 00 40 00 = some flags/config
    payload_raw = bytes([
        TE_SYSEX_FILE_INIT,
        0x01,
        0x00,
        0x40,
        0x00,
    ])
    payload = pack_7bit(payload_raw)
    full_payload = bytes([TE_SYSEX_FILE]) + payload
    return build_te_message(0x69, seq, full_payload)


# Upload constants
UPLOAD_CHUNK_SIZE = 433  # Bytes of audio per chunk after 7-bit unpacking


def build_upload_init_request(
    seq: int,
    slot: int,
    file_size: int,
    channels: int,
    samplerate: int = 44100,
    name: str | None = None
) -> bytes:
    """Build upload initialization message.

    This starts a sample upload to the given slot. The message includes:
    - Target slot/filename
    - File size
    - Audio metadata (channels, sample rate)

    Args:
        seq: Sequence number
        slot: Sound slot number (1-999)
        file_size: Size of audio data in bytes
        channels: Number of channels (1 or 2)
        samplerate: Sample rate (default 44100)
        name: Optional display name for the sample (default: slot number)

    Returns:
        Complete SysEx message
    """
    # Filename - use custom name if provided, otherwise slot number
    if name:
        filename = name.encode('utf-8')
    else:
        filename = f"{slot:03d}".encode('utf-8')

    # Metadata JSON
    metadata = f'{{"channels":{channels},"samplerate":{samplerate}}}'.encode('utf-8')

    # Build init payload - structure derived from capture analysis
    # Captured structure (unpacked):
    # [0] PUT op (0x02)
    # [1] unknown (0x00)
    # [2] file type (0x05 = audio?)
    # [3-4] target slot as 16-bit big-endian
    # [5-6] parent node (0x03e8 = 1000 = /sounds/)
    # [7-10] file size (32-bit big-endian)
    # [11+] filename + null + JSON

    # Encode file size in 4 bytes (big-endian)
    size_bytes = file_size.to_bytes(4, 'big')

    # Parent node is 1000 (sounds directory), encoded as 0x03e8
    parent_node = 1000

    # Build the raw payload that will be 7-bit encoded
    payload_raw = bytearray([
        TE_SYSEX_FILE_PUT,  # 0x02 = PUT operation
        0x00,  # Unknown
        0x05,  # File type (audio)
        (slot >> 8) & 0xFF,  # Target slot high byte
        slot & 0xFF,  # Target slot low byte
        (parent_node >> 8) & 0xFF,
        parent_node & 0xFF,
    ])
    payload_raw.extend(size_bytes)

    # Add filename (null-terminated)
    payload_raw.extend(filename)
    payload_raw.append(0x00)

    # Add metadata JSON (NOT null-terminated based on capture)
    payload_raw.extend(metadata)

    # Pack and build message
    payload = pack_7bit(bytes(payload_raw))
    full_payload = bytes([TE_SYSEX_FILE]) + payload
    return build_te_message(0x6c, seq, full_payload)


def build_upload_chunk_request(seq: int, chunk_index: int, audio_data: bytes) -> bytes:
    """Build data chunk message for sample upload.

    Each chunk can contain up to UPLOAD_CHUNK_SIZE bytes of audio data.
    The data is 7-bit encoded before transmission.

    Args:
        seq: Sequence number
        chunk_index: Chunk index (0-based, incrementing)
        audio_data: Raw PCM audio bytes (max 433 bytes per chunk)

    Returns:
        Complete SysEx message
    """
    if len(audio_data) > UPLOAD_CHUNK_SIZE:
        raise ValueError(f"Chunk too large: {len(audio_data)} > {UPLOAD_CHUNK_SIZE}")

    # Build chunk payload
    # Structure: PUT op, 0x01, chunk_index_hi, chunk_index_lo, audio_data
    payload_raw = bytearray([
        TE_SYSEX_FILE_PUT,  # 0x02 = PUT operation
        0x01,  # Indicates data chunk (vs init)
        (chunk_index >> 8) & 0xFF,
        chunk_index & 0xFF,
    ])
    payload_raw.extend(audio_data)

    # Pack and build message
    payload = pack_7bit(bytes(payload_raw))
    full_payload = bytes([TE_SYSEX_FILE]) + payload
    return build_te_message(0x6c, seq, full_payload)


def build_upload_end_request(seq: int, final_chunk_index: int) -> bytes:
    """Build end-of-upload marker message.

    This signals the device that the upload is complete.

    Args:
        seq: Sequence number
        final_chunk_index: Index of the last data chunk sent

    Returns:
        Complete SysEx message
    """
    # End marker uses same structure but with minimal data
    # From capture: the end marker has just the PUT op and chunk index
    payload_raw = bytes([
        TE_SYSEX_FILE_PUT,  # 0x02 = PUT operation
        0x01,
        (final_chunk_index >> 8) & 0xFF,
        final_chunk_index & 0xFF,
    ])

    payload = pack_7bit(payload_raw)
    full_payload = bytes([TE_SYSEX_FILE]) + payload
    # End marker uses command 0x6d (from capture)
    return build_te_message(0x6d, seq, full_payload)


# Pattern/Sequence commands (discovered 2024-11-30)
# Request -> Response mapping: cmd - 0x40 = response
PATTERN_CMD_LAYER_0A = 0x79  # Response 0x39 - Pattern data layer 0 (steps 29-156)
PATTERN_CMD_LAYER_0B = 0x7a  # Response 0x3a - Pattern data layer 0 (continued)
PATTERN_CMD_LAYER_1A = 0x7b  # Response 0x3b - Main sequence data (steps 29-156)
PATTERN_CMD_LAYER_1B = 0x7c  # Response 0x3c - Sequence data (continued)
PATTERN_CMD_LAYER_2 = 0x7d   # Response 0x3d - FX/automation data

# Pattern data constants
PATTERN_STEPS = 128          # Total steps per pattern
PATTERN_PADS = 12            # Pads per group
PATTERN_PAD_BYTES = 27       # Bytes per pad per step
PATTERN_CHUNK_SIZE = 327     # Total bytes per response chunk (3 header + 324 data)


def build_pattern_get_request(seq: int, layer: int, step_index: int) -> bytes:
    """Build a pattern data GET request message.

    Args:
        seq: Sequence number
        layer: Data layer (0, 1, or 2)
        step_index: Step index (0-255)

    Returns:
        Complete SysEx message
    """
    # Request payload: [GET, flag, layer, index]
    # GET = 0x03, flag = 0x01
    payload_raw = bytes([
        TE_SYSEX_FILE_GET,  # 0x03 = GET operation
        0x01,               # Flag
        layer & 0xFF,       # Layer type (0, 1, or 2)
        step_index & 0xFF,  # Step index
    ])
    payload = pack_7bit(payload_raw)
    full_payload = bytes([TE_SYSEX_FILE]) + payload

    # Select command based on layer and index range
    # Layer 0: 0x79 for indices 29-156, 0x7a for others (with MSB handling)
    # Layer 1: 0x7b for indices 29-156, 0x7c for others
    # Layer 2: 0x7d
    if layer == 0:
        cmd = PATTERN_CMD_LAYER_0A if 29 <= step_index <= 156 else PATTERN_CMD_LAYER_0B
    elif layer == 1:
        cmd = PATTERN_CMD_LAYER_1A if 29 <= step_index <= 156 else PATTERN_CMD_LAYER_1B
    else:
        cmd = PATTERN_CMD_LAYER_2

    return build_te_message(cmd, seq, full_payload)


def build_pattern_put_request(seq: int, layer: int, step_index: int, step_data: bytes) -> bytes:
    """Build a pattern data PUT request message.

    Args:
        seq: Sequence number
        layer: Data layer (0, 1, or 2)
        step_index: Step index (0-127)
        step_data: Step data (324 bytes = 12 pads × 27 bytes)

    Returns:
        Complete SysEx message

    Note:
        This is experimental - the exact PUT format needs verification.
        Based on the pattern that PUT uses 0x02 instead of GET's 0x03.
    """
    if len(step_data) != PATTERN_PADS * PATTERN_PAD_BYTES:
        raise ValueError(f"Step data must be {PATTERN_PADS * PATTERN_PAD_BYTES} bytes, got {len(step_data)}")

    # Request payload: [PUT, flag, layer, index, data...]
    # Hypothesis: PUT = 0x02, same structure as GET but with data appended
    payload_raw = bytearray([
        TE_SYSEX_FILE_PUT,  # 0x02 = PUT operation
        0x01,               # Flag
        layer & 0xFF,       # Layer type (0, 1, or 2)
        step_index & 0xFF,  # Step index
    ])
    payload_raw.extend(step_data)
    payload = pack_7bit(bytes(payload_raw))
    full_payload = bytes([TE_SYSEX_FILE]) + payload

    # Use same command selection as GET
    if layer == 0:
        cmd = PATTERN_CMD_LAYER_0A if 29 <= step_index <= 156 else PATTERN_CMD_LAYER_0B
    elif layer == 1:
        cmd = PATTERN_CMD_LAYER_1A if 29 <= step_index <= 156 else PATTERN_CMD_LAYER_1B
    else:
        cmd = PATTERN_CMD_LAYER_2

    return build_te_message(cmd, seq, full_payload)


def parse_pattern_response(payload: bytes) -> dict | None:
    """Parse decoded payload from a pattern data response.

    Args:
        payload: Decoded (unpacked) payload bytes (327 bytes expected)

    Returns:
        Dict with parsed pattern data, or None if invalid
    """
    if len(payload) < 3:
        return None

    flags = payload[0]
    layer = payload[1]
    step_index = payload[2]
    step_data = payload[3:] if len(payload) > 3 else b""

    # Parse per-pad data
    pads = []
    for pad in range(PATTERN_PADS):
        start = pad * PATTERN_PAD_BYTES
        end = start + PATTERN_PAD_BYTES
        if end <= len(step_data):
            pad_data = step_data[start:end]
            pads.append({
                "pad": pad + 1,
                "data": pad_data,
                "trigger": pad_data[0] if len(pad_data) > 0 else 0,
                "velocity": pad_data[1] if len(pad_data) > 1 else 0,
            })

    return {
        "flags": flags,
        "layer": layer,
        "step_index": step_index,
        "step_data": step_data,
        "pads": pads,
    }


def parse_file_list_response(payload: bytes) -> list[dict]:
    """Parse decoded payload from a FILE LIST response.

    Args:
        payload: Decoded (unpacked) payload bytes

    Returns:
        List of file entries with nodeId, flags, size, name
    """
    if len(payload) < 2:
        return []

    # Skip 2-byte header
    data = payload[2:]
    entries = []
    offset = 0

    while offset + 7 <= len(data):
        node_id = (data[offset] << 8) | data[offset + 1]
        flags = data[offset + 2]
        size = (data[offset + 3] << 24) | (data[offset + 4] << 16) | \
               (data[offset + 5] << 8) | data[offset + 6]
        offset += 7

        # Read null-terminated name
        name_bytes = bytearray()
        while offset < len(data) and data[offset] != 0:
            name_bytes.append(data[offset])
            offset += 1
        offset += 1  # Skip null terminator

        name = bytes(name_bytes).decode('utf-8', errors='replace')
        if name:
            entries.append({
                "node_id": node_id,
                "flags": flags,
                "size": size,
                "name": name,
                "is_dir": bool(flags & 0x02),
            })

    return entries
