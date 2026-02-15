"""S1000-family SysEx protocol encoding for S2800.

Pure functions for Akai character encoding, nibble encoding, and
SysEx message construction. No I/O, no state.

Message format: F0 47 [channel] [function] 48 [data...] F7
"""

# Akai manufacturer ID and S1000 family model ID
AKAI_MFR = 0x47
S1000_MODEL = 0x48

# S1000 function codes (confirmed on S2800 or per S1000 spec)
FUNC_RPLIST = 0x02     # Request program list
FUNC_PLIST = 0x03      # Program list response
FUNC_RSLIST = 0x04     # Request sample list
FUNC_SLIST = 0x05      # Sample list response
FUNC_RPDATA = 0x06     # Request program header
FUNC_PDATA = 0x07      # Send/receive program header
FUNC_RKDATA = 0x08     # Request keygroup header
FUNC_KDATA = 0x09      # Send/receive keygroup header
FUNC_RSDATA = 0x0A     # Request sample header
FUNC_SDATA = 0x0B      # Send/receive sample header
FUNC_ASPACK = 0x0D     # Accept SDS data packets
FUNC_DELP = 0x12       # Delete program
FUNC_DELS = 0x14       # Delete sample
FUNC_REPLY = 0x16      # Device reply (OK/error)
# S3000/S2800 extended function codes
FUNC_S3K_RPDATA = 0x27    # Request program header (S3000 format)
FUNC_S3K_PDATA = 0x28     # Send/receive program header (S3000 format)
FUNC_S3K_RKDATA = 0x29    # Request keygroup header (S3000 format)
FUNC_S3K_KDATA = 0x2A     # Send/receive keygroup header (S3000 format)
FUNC_S3K_RSDATA = 0x2B    # Request sample header (S3000 format)
FUNC_WRITE_SAMPLE_HDR = 0x2C  # Write sample header bytes at offset

# Reply codes (in FUNC_REPLY response)
REPLY_OK = 0x00
REPLY_ERROR = 0x01

# Akai character encoding table
AKAI_CHARS = "0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ#+-./"


def ascii_to_akai(c: str) -> int:
    """Convert a single ASCII character to Akai encoding."""
    c = c.upper()
    idx = AKAI_CHARS.find(c)
    if idx >= 0:
        return idx
    return 10  # space for unknown characters


def akai_to_ascii(code: int) -> str:
    """Convert an Akai character code to ASCII."""
    if code < len(AKAI_CHARS):
        return AKAI_CHARS[code]
    return "?"


def encode_akai_name(name: str, length: int = 12) -> bytes:
    """Encode a string as an Akai name, padded with spaces.

    Args:
        name: ASCII name (max `length` chars)
        length: Target length (default 12)

    Returns:
        Encoded bytes of exactly `length` bytes
    """
    result = bytearray()
    for i in range(length):
        if i < len(name):
            result.append(ascii_to_akai(name[i]))
        else:
            result.append(10)  # space padding
    return bytes(result)


def decode_akai_name(data: bytes) -> str:
    """Decode Akai-encoded name bytes to ASCII, stripping trailing spaces."""
    return "".join(akai_to_ascii(b) for b in data).rstrip()


def nibble_encode(data: bytes) -> bytes:
    """Encode raw bytes as low-nibble/high-nibble pairs.

    Each input byte produces two output bytes:
        byte 0xAB -> 0x0B (low nibble), 0x0A (high nibble)

    Args:
        data: Raw bytes to encode

    Returns:
        Nibble-encoded bytes (2x input length)
    """
    result = bytearray()
    for b in data:
        result.append(b & 0x0F)
        result.append((b >> 4) & 0x0F)
    return bytes(result)


def nibble_decode(data: bytes) -> bytes:
    """Decode nibble-encoded pairs back to raw bytes.

    Args:
        data: Nibble-encoded bytes (must be even length)

    Returns:
        Raw bytes (half the input length)
    """
    result = bytearray()
    for i in range(0, len(data) - 1, 2):
        lo = data[i] & 0x0F
        hi = data[i + 1] & 0x0F
        result.append(lo | (hi << 4))
    return bytes(result)


def build_message(channel: int, function: int, data: bytes = b"") -> bytes:
    """Build a complete S1000-family SysEx message.

    Format: F0 47 [channel] [function] 48 [data...] F7

    Args:
        channel: Exclusive channel (0x00 for channel 1)
        function: Function code (e.g. FUNC_SDATA)
        data: Payload bytes (already encoded as needed)

    Returns:
        Complete SysEx message bytes
    """
    msg = bytearray([
        0xF0,
        AKAI_MFR,
        channel & 0x7F,
        function & 0x7F,
        S1000_MODEL,
    ])
    msg.extend(data)
    msg.append(0xF7)
    return bytes(msg)


def parse_reply(data: bytes) -> tuple[int, bytes]:
    """Parse an S1000-family SysEx reply message.

    Args:
        data: Raw SysEx bytes including F0/F7

    Returns:
        Tuple of (function_code, payload_bytes)

    Raises:
        ValueError: If message is not a valid S1000-family message
    """
    if len(data) < 6:
        raise ValueError(f"Message too short: {len(data)} bytes")
    if data[0] != 0xF0 or data[-1] != 0xF7:
        raise ValueError("Missing SysEx start/end markers")
    if data[1] != AKAI_MFR:
        raise ValueError(f"Not Akai message: manufacturer 0x{data[1]:02X}")
    if data[4] != S1000_MODEL:
        raise ValueError(f"Not S1000 family: model 0x{data[4]:02X}")

    function = data[3]
    payload = bytes(data[5:-1])
    return function, payload
