"""CLI entry point for the S2800/S3000/S3200 SysEx protocol tool.

Replaces the bash wrapper with proper argument parsing. Handles negative
numbers, provides per-subcommand --help, and dispatches directly to the
tool functions in s2800.agent.tools.

Usage:
    python -m s2800.agent param FILFRQ
    python -m s2800.agent write PANPOS -- -50 1
    python -m s2800.agent --help
"""

import argparse
import sys

from s2800.agent.tools import (
    build_sysex_message,
    compare_models,
    decode_sysex_message,
    describe_agent,
    list_parameters,
    load_preset,
    lookup_by_offset,
    lookup_parameter,
    read_device_programs,
    read_device_samples,
    read_keygroup_parameter,
    read_memory_usage,
    read_program_parameter,
    read_program_summary,
    save_preset,
    write_keygroup_parameter,
    write_program_parameter,
)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="s2800-agent",
        description="S2800/S3000/S3200 SysEx Protocol Tool",
    )
    sub = parser.add_subparsers(dest="command")

    # -- Spec lookup commands ------------------------------------------------

    p = sub.add_parser("describe", help="Describe agent capabilities")
    p.set_defaults(func=lambda args: describe_agent())

    p = sub.add_parser("param", aliases=["parameter", "lookup"],
                       help="Look up a parameter by name")
    p.add_argument("name", help="Parameter name (e.g. FILFRQ)")
    p.add_argument("header", nargs="?", default="",
                   help="Header type: program, keygroup, or sample")
    p.set_defaults(func=lambda args: lookup_parameter(args.name, args.header))

    p = sub.add_parser("offset", help="Find parameter at a byte offset")
    p.add_argument("header", help="Header type: program, keygroup, or sample")
    p.add_argument("offset", type=int, help="Byte offset (0-191)")
    p.set_defaults(func=lambda args: lookup_by_offset(args.header, args.offset))

    p = sub.add_parser("list", help="List parameters for a header type")
    p.add_argument("header", help="Header type: program, keygroup, or sample")
    p.add_argument("filter", nargs="?", default="",
                   help="Filter by name or description")
    p.set_defaults(func=lambda args: list_parameters(args.header, args.filter))

    p = sub.add_parser("build", help="Build a SysEx message")
    p.add_argument("operation", help="Opcode or name (e.g. 0x27, request_program)")
    p.add_argument("channel", type=int, help="MIDI exclusive channel")
    p.add_argument("item", type=int, help="Item index")
    p.add_argument("selector", type=int, help="Selector byte")
    p.add_argument("offset", type=int, help="Byte offset")
    p.add_argument("length", type=int, help="Number of bytes")
    p.add_argument("data", type=int, nargs="*", help="Data bytes to include")
    p.set_defaults(func=lambda args: build_sysex_message(
        args.operation, args.channel, args.item, args.selector,
        args.offset, args.length, args.data or None,
    ))

    p = sub.add_parser("decode", help="Decode a SysEx hex string")
    p.add_argument("hex", help='Hex string (e.g. "F0 47 00 27 48 ...")')
    p.set_defaults(func=lambda args: decode_sysex_message(args.hex))

    p = sub.add_parser("models", aliases=["compare"],
                       help="Compare S2800/S3000/S3200 models")
    p.add_argument("param", nargs="?", default="",
                   help="Parameter name to compare across models")
    p.set_defaults(func=lambda args: compare_models(args.param))

    # -- Live device commands ------------------------------------------------

    p = sub.add_parser("programs", help="List programs on device")
    p.set_defaults(func=lambda args: read_device_programs())

    p = sub.add_parser("samples", help="List samples on device")
    p.set_defaults(func=lambda args: read_device_samples())

    p = sub.add_parser("read", help="Read a program parameter")
    p.add_argument("name", help="Parameter name (e.g. POLYPH)")
    p.add_argument("program", type=int, nargs="?", default=0,
                   help="Program number (default: 0)")
    p.set_defaults(func=lambda args: read_program_parameter(
        args.name, args.program,
    ))

    p = sub.add_parser("read-kg", help="Read a keygroup parameter")
    p.add_argument("name", help="Parameter name (e.g. FILFRQ)")
    p.add_argument("program", type=int, nargs="?", default=0,
                   help="Program number (default: 0)")
    p.add_argument("keygroup", type=int, nargs="?", default=0,
                   help="Keygroup number (default: 0)")
    p.set_defaults(func=lambda args: read_keygroup_parameter(
        args.name, args.program, args.keygroup,
    ))

    p = sub.add_parser("write", help="Write a program parameter")
    p.add_argument("name", help="Parameter name (e.g. POLYPH)")
    p.add_argument("value", type=int, help="Value to write")
    p.add_argument("program", type=int, nargs="?", default=0,
                   help="Program number (default: 0)")
    p.set_defaults(func=lambda args: write_program_parameter(
        args.name, args.value, args.program,
    ))

    p = sub.add_parser("write-kg", help="Write a keygroup parameter")
    p.add_argument("name", help="Parameter name (e.g. FILFRQ)")
    p.add_argument("value", type=int, help="Value to write")
    p.add_argument("program", type=int, nargs="?", default=0,
                   help="Program number (default: 0)")
    p.add_argument("keygroup", type=int, nargs="?", default=0,
                   help="Keygroup number (default: 0)")
    p.set_defaults(func=lambda args: write_keygroup_parameter(
        args.name, args.value, args.program, args.keygroup,
    ))

    p = sub.add_parser("summary", help="Full program settings summary")
    p.add_argument("program", type=int, nargs="?", default=0,
                   help="Program number (default: 0)")
    p.set_defaults(func=lambda args: read_program_summary(args.program))

    p = sub.add_parser("memory", aliases=["mem"],
                       help="Sample memory usage report")
    p.add_argument("total_words", type=int, nargs="?", default=None,
                   help="Total memory in 16-bit words (default: 8MB)")
    p.set_defaults(func=lambda args: (
        read_memory_usage(args.total_words)
        if args.total_words is not None
        else read_memory_usage()
    ))

    # -- Preset commands -----------------------------------------------------

    p = sub.add_parser("save-preset", help="Save program to preset JSON")
    p.add_argument("directory", help="Preset directory (e.g. presets/606_kit)")
    p.add_argument("program", type=int, nargs="?", default=0,
                   help="Program number (default: 0)")
    p.set_defaults(func=lambda args: save_preset(args.directory, args.program))

    p = sub.add_parser("load-preset", help="Restore preset to device")
    p.add_argument("directory", help="Preset directory (e.g. presets/606_kit)")
    p.add_argument("slot", type=int, nargs="?", default=None,
                   help="Target program slot (default: append)")
    p.set_defaults(func=lambda args: load_preset(args.directory, args.slot))

    # -- Parse and dispatch --------------------------------------------------

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    print(args.func(args))


if __name__ == "__main__":
    main()
