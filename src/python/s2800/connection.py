"""Shared S2800 device connection and low-level I/O.

This module provides the reusable device communication layer used by both
the agent tools (s2800.agent.tools) and other clients (web controller, tests).
It has no dependency on the agent layer and returns structured data, not
formatted text strings.
"""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

class SamplerConnection:
    """Lazy singleton connection to the S2800.

    Connects on first use and keeps the connection open for subsequent
    calls within the same process. Reconnects automatically if the
    connection is lost.
    """

    def __init__(self):
        self._sampler = None

    def get(self):
        """Get the shared S2800 connection, connecting if needed."""
        from s2800.sampler import S2800

        if self._sampler is not None:
            try:
                if self._sampler._port_in and self._sampler._port_out:
                    return self._sampler
            except Exception:
                pass
            self.close()

        self._sampler = S2800()
        self._sampler.open()
        logger.info("Connected to S2800 (persistent connection)")
        return self._sampler

    def close(self):
        """Explicitly close the connection."""
        if self._sampler is not None:
            try:
                self._sampler.close()
            except Exception:
                pass
            self._sampler = None


_default_connection = SamplerConnection()


def get_sampler():
    """Get the shared S2800 connection (lazy singleton)."""
    return _default_connection.get()


# ---------------------------------------------------------------------------
# Low-level SysEx write
# ---------------------------------------------------------------------------

def write_raw_bytes(sampler, opcode: int, program_number: int,
                    selector: int, offset: int, data: bytes) -> str | None:
    """Write raw bytes to a header via S3K partial write.

    Args:
        sampler: Connected S2800 instance.
        opcode: S3K write opcode (e.g. FUNC_S3K_KDATA = 0x2A).
        program_number: Program index.
        selector: Keygroup index (0 for program header writes).
        offset: Byte offset within the header.
        data: Raw bytes to write (nibble-encoded internally).

    Returns:
        None on success, error string on failure.
    """
    from s2800.protocol import FUNC_REPLY, REPLY_OK
    from s2800.protocol import nibble_encode

    nibbled = nibble_encode(data)
    payload = bytearray([
        program_number & 0x7F,
        (program_number >> 7) & 0x7F,
        selector & 0x7F,
        offset & 0x7F,
        (offset >> 7) & 0x7F,
        len(data) & 0x7F,
        (len(data) >> 7) & 0x7F,
    ])
    payload.extend(nibbled)
    sampler._send(opcode, bytes(payload))

    result = sampler._recv(timeout=3.0)
    time.sleep(0.1)

    if result and result[0] == FUNC_REPLY:
        code = result[1][0] if result[1] else 0
        if code != REPLY_OK:
            return f"Device rejected write (error code {code})"
    return None


# ---------------------------------------------------------------------------
# Batch keygroup state read
# ---------------------------------------------------------------------------

@dataclass
class KgField:
    """Descriptor for a single parameter within a keygroup header."""
    name: str
    offset: int
    size: int    # bytes (1 or 2)
    signed: bool = False


def read_kg_fields(program: int, kg_index: int,
                   fields: list[KgField]) -> dict[str, int] | None:
    """Read multiple keygroup header fields in one SysEx round-trip.

    Calls sampler.read_keygroup() once and extracts all requested fields
    from the raw bytes. Much more efficient than reading each parameter
    individually for state-loading use cases.

    Args:
        program: Program index.
        kg_index: Keygroup index.
        fields: List of KgField descriptors.

    Returns:
        Dict mapping field name → integer value, or None if read failed.
    """
    sampler = get_sampler()
    raw = sampler.read_keygroup(program, kg_index)
    if raw is None:
        return None

    result = {}
    for f in fields:
        b = raw[f.offset:f.offset + f.size]
        if f.size == 1:
            val = b[0]
        else:
            val = b[0] | (b[1] << 8)
        if f.signed:
            if f.size == 1 and val > 127:
                val -= 256
            elif f.size == 2 and val > 32767:
                val -= 65536
        result[f.name] = val

    return result


def write_kg_field(program: int, kg_index: int,
                   field: KgField, value: int) -> tuple[int, int] | str:
    """Write a single keygroup field and read back to confirm.

    Args:
        program: Program index.
        kg_index: Keygroup index.
        field: KgField descriptor for the parameter to write.
        value: Integer value to write.

    Returns:
        Tuple (old_value, new_value) on success, or error string on failure.
    """
    from s2800.protocol import FUNC_S3K_KDATA

    sampler = get_sampler()

    # Read current value
    current = read_kg_fields(program, kg_index, [field])
    if current is None:
        return f"Could not read current value of {field.name}"
    old_val = current[field.name]

    # Encode and write
    if field.size == 1:
        data = bytes([value & 0xFF])
    else:
        data = bytes([value & 0xFF, (value >> 8) & 0xFF])

    err = write_raw_bytes(sampler, FUNC_S3K_KDATA, program, kg_index,
                          field.offset, data)
    if err:
        return err

    # Read back
    confirmed = read_kg_fields(program, kg_index, [field])
    if confirmed is None:
        return old_val, value  # Could not confirm, assume success
    return old_val, confirmed[field.name]
