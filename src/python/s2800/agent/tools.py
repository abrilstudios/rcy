"""Tool functions for the S2800/S3000/S3200 SysEx expert agent.

These tools provide precise, non-hallucinated answers by querying the
structured specification data, using the existing protocol module for
message construction and parsing, and reading live values from a
connected S2800 sampler over MIDI.
"""

import logging

from s2800.agent.spec import (
    ALL_HEADERS,
    MODULATION_SOURCES,
    MODEL_DIFFERENCES,
    OPCODES,
    HeaderSpec,
    Parameter,
)
from s2800.protocol import (
    build_message,
    decode_akai_name,
    nibble_decode,
    nibble_encode,
)

logger = logging.getLogger(__name__)


def _format_parameter(param: Parameter, header_name: str = "") -> str:
    """Format a single parameter for display."""
    lines = []
    prefix = f"[{header_name}] " if header_name else ""
    lines.append(f"{prefix}{param.name}")
    lines.append(f"  Offset: {param.offset} (0x{param.offset:02X})")
    lines.append(f"  Size: {param.size} byte(s)")
    lines.append(f"  Range: {param.range_desc}")
    lines.append(f"  Description: {param.description}")
    if param.models != ["S2800", "S3000", "S3200"]:
        lines.append(f"  Models: {', '.join(param.models)}")
    if param.notes:
        lines.append(f"  Notes: {param.notes}")
    return "\n".join(lines)


def _fuzzy_match(query: str, name: str) -> bool:
    """Check if query matches a parameter name (case-insensitive, partial)."""
    return query.lower() in name.lower()


def _find_header(header_type: str) -> HeaderSpec | None:
    """Find a header spec by type name."""
    key = header_type.lower().strip()
    return ALL_HEADERS.get(key)


def lookup_parameter(name: str, header_type: str = "") -> str:
    """Look up a parameter by name (exact or fuzzy match).

    Returns offset, size, range, description, and model support.
    If header_type is empty, searches all headers.

    Args:
        name: Parameter name to search for (e.g. "FILFRQ", "filter freq").
        header_type: Optional header type to restrict search ("program",
            "keygroup", or "sample"). If empty, searches all headers.

    Returns:
        Formatted string with parameter details, or an error message if
        no match is found.
    """
    results = []
    headers_to_search = {}

    if header_type:
        header = _find_header(header_type)
        if not header:
            return (f"Unknown header type: '{header_type}'. "
                    f"Valid types: {', '.join(ALL_HEADERS.keys())}")
        headers_to_search = {header.name: header}
    else:
        headers_to_search = ALL_HEADERS

    query = name.strip()

    for hdr_name, hdr in headers_to_search.items():
        for param in hdr.parameters:
            # Exact match (case-insensitive)
            if param.name.lower() == query.lower():
                results.insert(0, _format_parameter(param, hdr_name))
            # Fuzzy match on name or description
            elif (_fuzzy_match(query, param.name)
                  or _fuzzy_match(query, param.description)):
                results.append(_format_parameter(param, hdr_name))

    if not results:
        return f"No parameter found matching '{name}'."

    header_info = f" (in {header_type} header)" if header_type else ""
    return (f"Found {len(results)} match(es){header_info}:\n\n"
            + "\n\n".join(results))


def lookup_by_offset(header_type: str, offset: int) -> str:
    """Reverse lookup: given a header type and byte offset, find the parameter.

    Args:
        header_type: Header type ("program", "keygroup", or "sample").
        offset: Byte offset within the header (0-191).

    Returns:
        Formatted string with the parameter at that offset, or an error
        message if no parameter is found.
    """
    header = _find_header(header_type)
    if not header:
        return (f"Unknown header type: '{header_type}'. "
                f"Valid types: {', '.join(ALL_HEADERS.keys())}")

    if offset < 0 or offset >= header.total_size:
        return (f"Offset {offset} is out of range for {header_type} header "
                f"(valid: 0-{header.total_size - 1}).")

    # Find exact offset match
    for param in header.parameters:
        if param.offset == offset:
            return _format_parameter(param, header.name)

    # Find parameter that spans this offset
    for param in header.parameters:
        if param.offset <= offset < param.offset + param.size:
            byte_within = offset - param.offset
            return (f"Offset {offset} is byte {byte_within} within:\n\n"
                    + _format_parameter(param, header.name))

    return (f"No parameter defined at offset {offset} in {header_type} header. "
            f"This offset may be in a reserved/unused region.")


def list_parameters(header_type: str, filter_text: str = "") -> str:
    """List all parameters for a header type, optionally filtered.

    Args:
        header_type: Header type ("program", "keygroup", or "sample").
        filter_text: Optional text to filter parameters by name or
            description. If empty, lists all parameters.

    Returns:
        Formatted table of parameters.
    """
    header = _find_header(header_type)
    if not header:
        return (f"Unknown header type: '{header_type}'. "
                f"Valid types: {', '.join(ALL_HEADERS.keys())}")

    params = header.parameters
    if filter_text:
        query = filter_text.lower()
        params = [
            p for p in params
            if query in p.name.lower() or query in p.description.lower()
        ]

    if not params:
        return (f"No parameters found in {header_type} header"
                + (f" matching '{filter_text}'" if filter_text else "")
                + ".")

    lines = [
        f"{header_type.upper()} HEADER ({header.total_size} bytes, "
        f"request: 0x{header.request_opcode:02X}, "
        f"response: 0x{header.response_opcode:02X})",
        "",
        f"{'Name':<14} {'Offset':>6} {'Size':>4}  {'Range':<30} Description",
        "-" * 90,
    ]

    for p in params:
        models_note = ""
        if p.models != ["S2800", "S3000", "S3200"]:
            models_note = f" [{','.join(p.models)}]"
        lines.append(
            f"{p.name:<14} {p.offset:>6} {p.size:>4}  "
            f"{p.range_desc:<30} {p.description}{models_note}"
        )

    lines.append(f"\nTotal: {len(params)} parameter(s)")
    return "\n".join(lines)


def build_sysex_message(
    operation: str,
    channel: int = 0,
    item_index: int = 0,
    selector: int = 0,
    offset: int = 0,
    length: int = 0,
    data_bytes: list[int] | None = None,
) -> str:
    """Construct a complete SysEx message from high-level parameters.

    Uses the existing protocol module for message construction and nibble
    encoding. If data_bytes is None, builds a request message (no data
    payload).

    Args:
        operation: Operation name or hex opcode (e.g. "request_program",
            "0x27", "program_header", "request_keygroup").
        channel: MIDI exclusive channel (0 for channel 1).
        item_index: Item number (program/sample/effect index, 14-bit).
        selector: Selector byte (keygroup number, data type, etc.).
        offset: Byte offset into the data item.
        length: Number of bytes to read/write.
        data_bytes: Optional list of raw data bytes to include in the
            message. These will be nibble-encoded. If None, builds a
            request (read) message.

    Returns:
        Hex string of the complete SysEx message with explanation.
    """
    # Resolve operation to opcode
    opcode = _resolve_opcode(operation)
    if opcode is None:
        return (f"Unknown operation: '{operation}'. Use an opcode like '0x27' "
                f"or a name like 'request_program', 'keygroup_header', etc.")

    # Build the 7-byte header data portion (after the 5-byte SysEx header)
    # Bytes 5-6: item index (14-bit, low 7 bits then high 7 bits)
    idx_lo = item_index & 0x7F
    idx_hi = (item_index >> 7) & 0x7F
    # Byte 7: selector
    sel = selector & 0x7F
    # Bytes 8-9: offset (low 7 bits then high 7 bits)
    off_lo = offset & 0x7F
    off_hi = (offset >> 7) & 0x7F
    # Bytes 10-11: length (low 7 bits then high 7 bits)
    len_lo = length & 0x7F
    len_hi = (length >> 7) & 0x7F

    payload = bytes([idx_lo, idx_hi, sel, off_lo, off_hi, len_lo, len_hi])

    # Append nibble-encoded data if provided
    if data_bytes is not None:
        raw_data = bytes(data_bytes)
        encoded = nibble_encode(raw_data)
        payload = payload + encoded

    msg = build_message(channel, opcode, payload)
    hex_str = " ".join(f"{b:02X}" for b in msg)

    # Build explanation
    op_info = _get_opcode_info(opcode)
    explanation = [
        f"SysEx Message ({len(msg)} bytes):",
        f"  Hex: {hex_str}",
        "",
        "  Breakdown:",
        f"    F0          - SysEx start",
        f"    47          - Akai manufacturer ID",
        f"    {channel:02X}          - Exclusive channel {channel + 1}",
        f"    {opcode:02X}          - {op_info}",
        f"    48          - S1000/S3000 model ID",
        f"    {idx_lo:02X} {idx_hi:02X}      - Item index: {item_index}",
        f"    {sel:02X}          - Selector: {selector}",
        f"    {off_lo:02X} {off_hi:02X}      - Offset: {offset}",
        f"    {len_lo:02X} {len_hi:02X}      - Length: {length} bytes",
    ]

    if data_bytes is not None:
        data_hex = " ".join(f"{b:02X}" for b in data_bytes)
        encoded_hex = " ".join(f"{b:02X}" for b in nibble_encode(bytes(data_bytes)))
        explanation.append(f"    {encoded_hex} - Data (nibble-encoded): [{data_hex}]")

    explanation.append(f"    F7          - SysEx end")

    return "\n".join(explanation)


def decode_sysex_message(hex_string: str) -> str:
    """Parse a raw SysEx hex string into human-readable form.

    Identifies the operation, channel, item index, selector, offset,
    length, and decodes any nibble-encoded data payload. Cross-references
    parameters at the given offset.

    Args:
        hex_string: Hex string of SysEx bytes, e.g.
            "F0 47 00 27 48 00 00 00 03 00 0C 00 F7" or
            "F04700274800000003000C00F7".

    Returns:
        Human-readable breakdown of the message.
    """
    # Parse hex string to bytes
    cleaned = hex_string.replace(" ", "").replace(",", "").replace("0x", "")
    if len(cleaned) % 2 != 0:
        return f"Invalid hex string: odd number of characters ({len(cleaned)})"

    try:
        msg_bytes = bytes.fromhex(cleaned)
    except ValueError as e:
        return f"Invalid hex string: {e}"

    if len(msg_bytes) < 12:
        return (f"Message too short ({len(msg_bytes)} bytes). "
                f"Minimum S3000 SysEx message is 12 bytes (header only, no data).")

    # Validate structure
    if msg_bytes[0] != 0xF0:
        return f"Not a SysEx message: first byte is 0x{msg_bytes[0]:02X}, expected 0xF0"
    if msg_bytes[-1] != 0xF7:
        return f"Missing SysEx end marker: last byte is 0x{msg_bytes[-1]:02X}, expected 0xF7"
    if msg_bytes[1] != 0x47:
        return f"Not an Akai message: manufacturer 0x{msg_bytes[1]:02X}, expected 0x47"
    if msg_bytes[4] != 0x48:
        return f"Not S1000/S3000 family: model 0x{msg_bytes[4]:02X}, expected 0x48"

    channel = msg_bytes[2]
    opcode = msg_bytes[3]
    item_lo = msg_bytes[5]
    item_hi = msg_bytes[6]
    item_index = item_lo | (item_hi << 7)
    selector = msg_bytes[7]
    offset_lo = msg_bytes[8]
    offset_hi = msg_bytes[9]
    offset = offset_lo | (offset_hi << 7)
    length_lo = msg_bytes[10]
    length_hi = msg_bytes[11]
    length = length_lo | (length_hi << 7)

    # Check post-change flags in item index
    postpone_screen = bool(item_hi & 0x40)  # bit 13
    postpone_recalc = bool(item_hi & 0x20)  # bit 12
    actual_item = item_lo | ((item_hi & 0x1F) << 7)

    op_info = _get_opcode_info(opcode)

    lines = [
        f"Decoded SysEx Message ({len(msg_bytes)} bytes):",
        f"  Operation: 0x{opcode:02X} - {op_info}",
        f"  Channel: {channel} (exclusive channel {channel + 1})",
        f"  Item Index: {actual_item}",
    ]

    if postpone_screen:
        lines.append("  Flag: Postpone screen update (bit 13 set)")
    if postpone_recalc:
        lines.append("  Flag: Postpone program recalculation (bit 12 set)")

    lines.extend([
        f"  Selector: {selector}",
        f"  Offset: {offset} (0x{offset:02X})",
        f"  Length: {length} bytes",
    ])

    # Decode data payload if present
    data_portion = msg_bytes[12:-1]
    if data_portion:
        decoded = nibble_decode(data_portion)
        decoded_hex = " ".join(f"0x{b:02X}" for b in decoded)
        lines.append(f"  Data ({len(decoded)} bytes): [{decoded_hex}]")

        # Try to decode as Akai name if it looks like name data
        if len(decoded) >= 6:
            try:
                name = decode_akai_name(decoded)
                if name and all(c.isprintable() for c in name):
                    lines.append(f"  As Akai name: \"{name}\"")
            except (ValueError, IndexError):
                pass
    else:
        lines.append("  Data: (none - this is a request/read message)")

    # Cross-reference parameters at the given offset
    header_type = _opcode_to_header_type(opcode)
    if header_type:
        param_info = lookup_by_offset(header_type, offset)
        if "No parameter" not in param_info:
            lines.append(f"\n  Parameter at offset {offset}:")
            for line in param_info.split("\n"):
                lines.append(f"    {line}")

    return "\n".join(lines)


def compare_models(parameter_name: str = "") -> str:
    """Show differences between S2800, S3000, and S3200 models.

    If a parameter name is given, shows model-specific behavior for that
    parameter. If empty, shows a summary of all model differences.

    Args:
        parameter_name: Optional parameter name to show model-specific
            behavior for. If empty, shows full comparison.

    Returns:
        Formatted comparison text.
    """
    if not parameter_name:
        lines = ["S2800 / S3000 / S3200 Model Comparison", "=" * 50, ""]
        for category, models in MODEL_DIFFERENCES.items():
            lines.append(f"{category.upper().replace('_', ' ')}:")
            for model, desc in models.items():
                lines.append(f"  {model}: {desc}")
            lines.append("")
        return "\n".join(lines)

    # Look up the specific parameter across all headers
    results = []
    query = parameter_name.strip().lower()

    for hdr_name, hdr in ALL_HEADERS.items():
        for param in hdr.parameters:
            if (param.name.lower() == query
                    or _fuzzy_match(query, param.name)):
                results.append((hdr_name, param))

    if not results:
        return (f"No parameter found matching '{parameter_name}'. "
                f"Try using lookup_parameter for a broader search.")

    lines = [f"Model comparison for '{parameter_name}':", ""]
    for hdr_name, param in results:
        lines.append(_format_parameter(param, hdr_name))
        lines.append("")

        if param.models != ["S2800", "S3000", "S3200"]:
            lines.append(f"  Availability: {', '.join(param.models)} only")
            missing = [m for m in ["S2800", "S3000", "S3200"]
                       if m not in param.models]
            if missing:
                lines.append(f"  Not available on: {', '.join(missing)}")
        else:
            # Check if there are range differences noted
            if "S3200" in param.range_desc or "S3000" in param.range_desc or "S2800" in param.range_desc:
                lines.append("  Range varies by model (see Range field above)")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_opcode(operation: str) -> int | None:
    """Resolve an operation string to a numeric opcode."""
    # Try direct hex
    op = operation.strip().lower()
    if op.startswith("0x"):
        try:
            return int(op, 16)
        except ValueError:
            return None

    # Try as decimal
    try:
        return int(op)
    except ValueError:
        pass

    # Map common names to opcodes
    name_map = {
        "request_program": 0x27,
        "request program": 0x27,
        "req_program": 0x27,
        "program_header": 0x28,
        "program header": 0x28,
        "send_program": 0x28,
        "request_keygroup": 0x29,
        "request keygroup": 0x29,
        "req_keygroup": 0x29,
        "keygroup_header": 0x2A,
        "keygroup header": 0x2A,
        "send_keygroup": 0x2A,
        "request_sample": 0x2B,
        "request sample": 0x2B,
        "req_sample": 0x2B,
        "sample_header": 0x2C,
        "sample header": 0x2C,
        "send_sample": 0x2C,
        "request_fx": 0x2D,
        "request fx": 0x2D,
        "request_reverb": 0x2D,
        "fx_data": 0x2E,
        "reverb_data": 0x2E,
        "request_cuelist": 0x2F,
        "request cue list": 0x2F,
        "cuelist_data": 0x30,
        "request_takelist": 0x31,
        "request take list": 0x31,
        "takelist_data": 0x32,
        "request_misc": 0x33,
        "request miscellaneous": 0x33,
        "misc_data": 0x34,
        "request_volume": 0x35,
        "request volume list": 0x35,
        "volume_data": 0x36,
        "request_hd": 0x37,
        "request harddisk": 0x37,
        "request hd directory": 0x37,
        "hd_data": 0x38,
    }

    return name_map.get(op)


def _get_opcode_info(opcode: int) -> str:
    """Get a human-readable description for an opcode."""
    for op in OPCODES:
        if op.code == opcode:
            return f"{op.name} ({op.direction})"
    return f"Unknown opcode 0x{opcode:02X}"


def _opcode_to_header_type(opcode: int) -> str | None:
    """Map an opcode to the header type it operates on."""
    mapping = {
        0x27: "program",
        0x28: "program",
        0x29: "keygroup",
        0x2A: "keygroup",
        0x2B: "sample",
        0x2C: "sample",
    }
    return mapping.get(opcode)


# ---------------------------------------------------------------------------
# Live device tools
# ---------------------------------------------------------------------------

def _interpret_value(param: Parameter, raw_value: int) -> str:
    """Interpret a raw byte value using the parameter's range description."""
    range_desc = param.range_desc.lower()

    # Boolean/enum style: "0=OFF, 1=ON"
    if "=" in param.range_desc:
        for part in param.range_desc.split(","):
            part = part.strip()
            if "=" in part:
                val_str, label = part.split("=", 1)
                try:
                    if int(val_str.strip()) == raw_value:
                        return f"{raw_value} ({label.strip()})"
                except ValueError:
                    pass

    # Signed range like "-50 to +50"
    if "to" in range_desc and "-" in range_desc:
        if raw_value > 127:
            signed = raw_value - 256
        elif raw_value > 50 and "+50" in range_desc:
            signed = raw_value - 256 if raw_value > 127 else raw_value
        else:
            signed = raw_value
        return str(signed)

    # "represents 1-32 voices" style
    if "represents" in range_desc and "voices" in range_desc:
        return f"{raw_value} (= {raw_value + 1} voices)"

    # Mod source
    if "mod source" in range_desc:
        for src in MODULATION_SOURCES:
            if src.value == raw_value:
                return f"{raw_value} ({src.name})"

    return str(raw_value)


class _SamplerConnection:
    """Lazy singleton connection to the S2800.

    Connects on first use and keeps the connection open for subsequent
    tool calls within the same process. Reconnects automatically if the
    connection is lost.
    """

    def __init__(self):
        self._sampler = None

    def get(self):
        """Get the shared S2800 connection, connecting if needed."""
        from s2800.sampler import S2800

        if self._sampler is not None:
            # Verify the connection is still alive
            try:
                if self._sampler._port_in and self._sampler._port_out:
                    return self._sampler
            except Exception:
                pass
            # Connection lost, reconnect
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


_sampler_conn = _SamplerConnection()


def _get_sampler():
    """Get the shared S2800 connection."""
    return _sampler_conn.get()


def read_device_programs() -> str:
    """List all programs currently on the connected S2800.

    Connects to the S2800 over MIDI and retrieves the program list.
    No parameters required.

    Returns:
        List of program names with their indices, or an error message
        if the device is not connected.
    """
    try:
        sampler = _get_sampler()
    except Exception as e:
        return f"Could not connect to S2800: {e}"

    try:
        programs = sampler.list_programs()
        if not programs:
            return "No programs found on device."
        lines = [f"Programs on device ({len(programs)}):"]
        for i, name in enumerate(programs):
            lines.append(f"  {i}: {name}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading programs: {e}"


def read_device_samples() -> str:
    """List all samples currently on the connected S2800.

    Connects to the S2800 over MIDI and retrieves the sample list.
    No parameters required.

    Returns:
        List of sample names with their indices, or an error message
        if the device is not connected.
    """
    try:
        sampler = _get_sampler()
    except Exception as e:
        return f"Could not connect to S2800: {e}"

    try:
        samples = sampler.list_samples()
        if not samples:
            return "No samples found on device."
        lines = [f"Samples on device ({len(samples)}):"]
        for i, name in enumerate(samples):
            lines.append(f"  {i}: {name}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading samples: {e}"


def read_program_parameter(
    parameter_name: str,
    program_number: int = 0,
) -> str:
    """Read a parameter's current value from a program on the connected S2800.

    Connects to the device, reads the program header, extracts the
    parameter value, and cross-references it with the spec to give
    a meaningful interpretation.

    Args:
        parameter_name: Parameter name (e.g. "POLYPH", "LEGATO", "PRNAME").
        program_number: Program index (0-based, default 0).

    Returns:
        The current value with interpretation, or an error message.
    """
    # Find the parameter in the program header spec
    header = ALL_HEADERS["program"]
    param = None
    for p in header.parameters:
        if p.name.lower() == parameter_name.strip().lower():
            param = p
            break

    if param is None:
        # Try fuzzy match
        matches = []
        for p in header.parameters:
            if _fuzzy_match(parameter_name, p.name):
                matches.append(p)
        if len(matches) == 1:
            param = matches[0]
        elif matches:
            names = ", ".join(m.name for m in matches)
            return f"Ambiguous parameter '{parameter_name}'. Matches: {names}"
        else:
            return (f"Parameter '{parameter_name}' not found in program header. "
                    f"Use list_parameters('program') to see all parameters.")

    try:
        sampler = _get_sampler()
    except Exception as e:
        return f"Could not connect to S2800: {e}"

    try:
        raw_header = sampler.read_program_header(program_number)
        if raw_header is None:
            return f"No response from device for program {program_number}."

        if param.offset + param.size > len(raw_header):
            return (f"Header too short ({len(raw_header)} bytes) to read "
                    f"{param.name} at offset {param.offset}.")

        raw_bytes = raw_header[param.offset:param.offset + param.size]

        # Format the result
        lines = [f"Program {program_number}, {param.name}:"]

        if param.size == 1:
            value = raw_bytes[0]
            interpreted = _interpret_value(param, value)
            lines.append(f"  Current value: {interpreted}")
        elif param.name == "PRNAME" or "name" in param.name.lower():
            name = decode_akai_name(raw_bytes)
            lines.append(f"  Current value: \"{name}\"")
        elif param.size == 2:
            value = raw_bytes[0] | (raw_bytes[1] << 8)
            lines.append(f"  Current value: {value} (raw: 0x{raw_bytes[0]:02X} 0x{raw_bytes[1]:02X})")
        else:
            hex_str = " ".join(f"0x{b:02X}" for b in raw_bytes)
            lines.append(f"  Current value (raw): {hex_str}")

        lines.append(f"  Range: {param.range_desc}")
        lines.append(f"  Description: {param.description}")
        if param.notes:
            lines.append(f"  Notes: {param.notes}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error reading from device: {e}"


def read_keygroup_parameter(
    parameter_name: str,
    program_number: int = 0,
    keygroup_number: int = 0,
) -> str:
    """Read a parameter's current value from a keygroup on the connected S2800.

    Connects to the device, reads the keygroup header, extracts the
    parameter value, and cross-references it with the spec.

    Args:
        parameter_name: Parameter name (e.g. "FILFRQ", "SNAME1", "LONOTE").
        program_number: Program index (0-based, default 0).
        keygroup_number: Keygroup index (0-based, default 0).

    Returns:
        The current value with interpretation, or an error message.
    """
    header = ALL_HEADERS["keygroup"]
    param = None
    for p in header.parameters:
        if p.name.lower() == parameter_name.strip().lower():
            param = p
            break

    if param is None:
        matches = []
        for p in header.parameters:
            if _fuzzy_match(parameter_name, p.name):
                matches.append(p)
        if len(matches) == 1:
            param = matches[0]
        elif matches:
            names = ", ".join(m.name for m in matches)
            return f"Ambiguous parameter '{parameter_name}'. Matches: {names}"
        else:
            return (f"Parameter '{parameter_name}' not found in keygroup header. "
                    f"Use list_parameters('keygroup') to see all parameters.")

    try:
        sampler = _get_sampler()
    except Exception as e:
        return f"Could not connect to S2800: {e}"

    try:
        raw_header = sampler.read_keygroup(program_number, keygroup_number)
        if raw_header is None:
            return (f"No response from device for program {program_number}, "
                    f"keygroup {keygroup_number}.")

        if param.offset + param.size > len(raw_header):
            return (f"Header too short ({len(raw_header)} bytes) to read "
                    f"{param.name} at offset {param.offset}.")

        raw_bytes = raw_header[param.offset:param.offset + param.size]

        lines = [f"Program {program_number} / Keygroup {keygroup_number}, {param.name}:"]

        if "name" in param.name.lower() or "SNAME" in param.name:
            name = decode_akai_name(raw_bytes)
            lines.append(f"  Current value: \"{name}\"")
        elif param.size == 1:
            value = raw_bytes[0]
            interpreted = _interpret_value(param, value)
            lines.append(f"  Current value: {interpreted}")
        elif param.size == 2:
            value = raw_bytes[0] | (raw_bytes[1] << 8)
            lines.append(f"  Current value: {value} (raw: 0x{raw_bytes[0]:02X} 0x{raw_bytes[1]:02X})")
        else:
            hex_str = " ".join(f"0x{b:02X}" for b in raw_bytes)
            lines.append(f"  Current value (raw): {hex_str}")

        lines.append(f"  Range: {param.range_desc}")
        lines.append(f"  Description: {param.description}")
        if param.notes:
            lines.append(f"  Notes: {param.notes}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error reading from device: {e}"


def read_program_summary(program_number: int = 0) -> str:
    """Read key settings from a program on the connected S2800.

    Reads the full program header and returns a summary of the most
    important parameters: name, MIDI channel, polyphony, priority,
    play range, output routing, loudness, LFO settings, legato mode,
    and keygroup count.

    Args:
        program_number: Program index (0-based, default 0).

    Returns:
        Formatted summary of program settings.
    """
    try:
        sampler = _get_sampler()
    except Exception as e:
        return f"Could not connect to S2800: {e}"

    try:
        raw = sampler.read_program_header(program_number)
        if raw is None:
            return f"No response from device for program {program_number}."

        header = ALL_HEADERS["program"]

        lines = [f"Program {program_number} Summary:", ""]

        # Read key parameters by name
        key_params = [
            "PRNAME", "PRGNUM", "PMCHAN", "POLYPH", "PRIORT",
            "PLAYLO", "PLAYHI", "OUTPUT", "PANPOS", "PRLOUD",
            "LFORAT", "LFODEP", "B_PTCH", "B_PTCHD", "KXFADE",
            "GROUPS", "LEGATO", "B_MODE", "TRANSPOSE", "PFXCHAN",
        ]

        for pname in key_params:
            for p in header.parameters:
                if p.name == pname:
                    if p.offset + p.size > len(raw):
                        continue
                    raw_bytes = raw[p.offset:p.offset + p.size]

                    if pname == "PRNAME":
                        val_str = f"\"{decode_akai_name(raw_bytes)}\""
                    elif p.size == 1:
                        val_str = _interpret_value(p, raw_bytes[0])
                    elif p.size == 2:
                        val = raw_bytes[0] | (raw_bytes[1] << 8)
                        val_str = str(val)
                    else:
                        val_str = " ".join(f"0x{b:02X}" for b in raw_bytes)

                    lines.append(f"  {pname:<12} = {val_str:<20} ({p.description})")
                    break

        return "\n".join(lines)

    except Exception as e:
        return f"Error reading from device: {e}"


# ---------------------------------------------------------------------------
# Live device tools (write)
# ---------------------------------------------------------------------------

def _find_param(header_name: str, parameter_name: str) -> Parameter | str:
    """Find a parameter by name in a header. Returns Parameter or error string."""
    header = ALL_HEADERS[header_name]
    query = parameter_name.strip().lower()

    for p in header.parameters:
        if p.name.lower() == query:
            return p

    matches = [p for p in header.parameters if _fuzzy_match(query, p.name)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        names = ", ".join(m.name for m in matches)
        return f"Ambiguous parameter '{parameter_name}'. Matches: {names}"
    return (f"Parameter '{parameter_name}' not found in {header_name} header. "
            f"Use list_parameters('{header_name}') to see all parameters.")


def _write_raw_bytes(sampler, opcode: int, program_number: int,
                     selector: int, offset: int, data: bytes) -> str | None:
    """Write raw bytes to a header via S3K partial write. Returns error or None."""
    import time
    from s2800.protocol import FUNC_REPLY, REPLY_OK

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


def write_program_parameter(
    parameter_name: str,
    value: int,
    program_number: int = 0,
) -> str:
    """Write a value to a program parameter on the connected S2800.

    Looks up the parameter in the spec, validates it, writes the value
    via S3K partial write (opcode 0x28), then reads it back to confirm.

    Args:
        parameter_name: Parameter name (e.g. "POLYPH", "LEGATO", "PANPOS").
        value: Value to write (integer, 0-255 for single-byte parameters).
        program_number: Program index (0-based, default 0).

    Returns:
        Confirmation with before/after values, or an error message.
    """
    from s2800.protocol import FUNC_S3K_PDATA

    result = _find_param("program", parameter_name)
    if isinstance(result, str):
        return result
    param = result

    if "read-only" in param.notes.lower() or "internal" in param.notes.lower():
        return (f"Parameter {param.name} is {param.notes}. "
                f"Writing to it may be ignored by the device.")

    if param.size > 2:
        return (f"Parameter {param.name} is {param.size} bytes. "
                f"Use write_program_parameter only for 1-2 byte parameters.")

    try:
        sampler = _get_sampler()
    except Exception as e:
        return f"Could not connect to S2800: {e}"

    try:
        # Read current value first
        raw_header = sampler.read_program_header(program_number)
        if raw_header is None:
            return f"No response from device for program {program_number}."

        old_bytes = raw_header[param.offset:param.offset + param.size]
        old_val = old_bytes[0] if param.size == 1 else (old_bytes[0] | (old_bytes[1] << 8))

        # Write new value
        if param.size == 1:
            data = bytes([value & 0xFF])
        else:
            data = bytes([value & 0xFF, (value >> 8) & 0xFF])

        err = _write_raw_bytes(sampler, FUNC_S3K_PDATA, program_number,
                               0x00, param.offset, data)
        if err:
            return f"Write failed for {param.name}: {err}"

        # Read back to confirm
        new_header = sampler.read_program_header(program_number)
        if new_header:
            new_bytes = new_header[param.offset:param.offset + param.size]
            new_val = new_bytes[0] if param.size == 1 else (new_bytes[0] | (new_bytes[1] << 8))
            old_str = _interpret_value(param, old_val)
            new_str = _interpret_value(param, new_val)
            return (f"Program {program_number}, {param.name}:\n"
                    f"  Before: {old_str}\n"
                    f"  After:  {new_str}\n"
                    f"  ({param.description})")
        else:
            return (f"Wrote {param.name} = {value} on program {program_number} "
                    f"(could not read back to confirm).")

    except Exception as e:
        return f"Error writing to device: {e}"


def write_keygroup_parameter(
    parameter_name: str,
    value: int,
    program_number: int = 0,
    keygroup_number: int = 0,
) -> str:
    """Write a value to a keygroup parameter on the connected S2800.

    Looks up the parameter in the spec, validates it, writes the value
    via S3K partial write (opcode 0x2A), then reads it back to confirm.

    Args:
        parameter_name: Parameter name (e.g. "kgmute", "FILFRQ", "LONOTE").
        value: Value to write (integer, 0-255 for single-byte parameters).
        program_number: Program index (0-based, default 0).
        keygroup_number: Keygroup index (0-based, default 0).

    Returns:
        Confirmation with before/after values, or an error message.
    """
    from s2800.protocol import FUNC_S3K_KDATA

    result = _find_param("keygroup", parameter_name)
    if isinstance(result, str):
        return result
    param = result

    if "internal" in param.notes.lower():
        return (f"Parameter {param.name} is {param.notes}. "
                f"Writing to it may be ignored by the device.")

    if param.size > 2:
        return (f"Parameter {param.name} is {param.size} bytes. "
                f"Use write_keygroup_parameter only for 1-2 byte parameters.")

    try:
        sampler = _get_sampler()
    except Exception as e:
        return f"Could not connect to S2800: {e}"

    try:
        # Read current value first
        raw_header = sampler.read_keygroup(program_number, keygroup_number)
        if raw_header is None:
            return (f"No response from device for program {program_number}, "
                    f"keygroup {keygroup_number}.")

        old_bytes = raw_header[param.offset:param.offset + param.size]
        old_val = old_bytes[0] if param.size == 1 else (old_bytes[0] | (old_bytes[1] << 8))

        # Write new value
        if param.size == 1:
            data = bytes([value & 0xFF])
        else:
            data = bytes([value & 0xFF, (value >> 8) & 0xFF])

        err = _write_raw_bytes(sampler, FUNC_S3K_KDATA, program_number,
                               keygroup_number, param.offset, data)
        if err:
            return f"Write failed for {param.name}: {err}"

        # Read back to confirm
        new_header = sampler.read_keygroup(program_number, keygroup_number)
        if new_header:
            new_bytes = new_header[param.offset:param.offset + param.size]
            new_val = new_bytes[0] if param.size == 1 else (new_bytes[0] | (new_bytes[1] << 8))
            old_str = _interpret_value(param, old_val)
            new_str = _interpret_value(param, new_val)
            return (f"Program {program_number} / Keygroup {keygroup_number}, {param.name}:\n"
                    f"  Before: {old_str}\n"
                    f"  After:  {new_str}\n"
                    f"  ({param.description})")
        else:
            return (f"Wrote {param.name} = {value} on program {program_number} / "
                    f"keygroup {keygroup_number} (could not read back to confirm).")

    except Exception as e:
        return f"Error writing to device: {e}"
