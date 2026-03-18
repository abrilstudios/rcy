"""Shared MIDI port detection by name pattern."""

import mido


def find_ports(patterns: list[str]) -> tuple[str | None, str | None]:
    """Find MIDI input/output ports matching any of the given name patterns.

    Checks each pattern in order; returns the first match for input and output.

    Args:
        patterns: Port name substrings to try, in priority order.

    Returns:
        Tuple of (input_port_name, output_port_name), either may be None.
    """
    inputs = mido.get_input_names()
    outputs = mido.get_output_names()

    in_port = None
    out_port = None

    for pattern in patterns:
        if in_port is None:
            in_port = next((n for n in inputs if pattern in n), None)
        if out_port is None:
            out_port = next((n for n in outputs if pattern in n), None)

    return in_port, out_port
