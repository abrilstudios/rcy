#!/usr/bin/env python3
"""Akai MPC2000XL CLI.

Upload samples to the MPC2000XL over MIDI using SDS.

The MPC must be in receive mode before uploading:
    SHIFT + MIDI/SYNC > DUMP [F2]  (stay on that screen during transfer)

Usage:
    mpc ports                           List MIDI ports
    mpc upload <wav> [--slot N]         Upload WAV to sample slot

Examples:
    mpc ports
    mpc upload sounds/909/BD_909_Tape_Short_E_05.wav
    mpc upload kick.wav --slot 2
    mpc upload kick.wav --in "Volt 2" --out "Volt 2"
"""

import argparse
import sys
import time
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent.parent / "src" / "python"
sys.path.insert(0, str(src_path))

import numpy as np
import soundfile as sf

from mpc2000xl import MPC2000XL
from mpc2000xl.device import MPC2000XLError


def load_wav(path: Path) -> tuple[bytes, int]:
    """Load WAV file as mono 16-bit PCM. Returns (pcm_bytes, sample_rate)."""
    data, rate = sf.read(str(path), dtype='float32')
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    pcm = np.clip(data, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16).tobytes()
    return pcm, rate


def cmd_ports(args):
    inputs, outputs = MPC2000XL.list_ports()

    print("MIDI Input Ports:")
    for i, name in enumerate(inputs):
        print(f"  [{i}] {name}")
    if not inputs:
        print("  (none)")

    print()
    print("MIDI Output Ports:")
    for i, name in enumerate(outputs):
        print(f"  [{i}] {name}")
    if not outputs:
        print("  (none)")

    found_in, found_out = MPC2000XL.find_ports()
    print()
    if found_in and found_out:
        print(f"Auto-detected MPC2000XL:")
        print(f"  Input:  {found_in}")
        print(f"  Output: {found_out}")
    else:
        print("MPC2000XL not auto-detected. Use --in/--out to specify ports.")

    return 0


def cmd_upload(args):
    wav_path = Path(args.wav_file)

    if not wav_path.exists():
        print(f"File not found: {wav_path}")
        return 1

    print(f"Loading {wav_path.name}...")
    try:
        pcm, rate = load_wav(wav_path)
    except Exception as e:
        print(f"Failed to load audio: {e}")
        return 1

    num_samples = len(pcm) // 2
    duration = num_samples / rate
    packets = (num_samples * 3 + 119) // 120

    print(f"  {rate}Hz, {duration:.2f}s, {num_samples} samples")
    print(f"  Packets: {packets}")
    print()
    print("Make sure the MPC is on SHIFT+MIDI/SYNC > DUMP [F2] receive screen.")

    mpc = MPC2000XL(port_in=args.input_port, port_out=args.output_port)

    try:
        mpc.open()
    except MPC2000XLError as e:
        print(f"Connection failed: {e}")
        return 1

    try:
        start = time.time()

        def progress(done, total):
            elapsed = time.time() - start
            rate_pps = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate_pps if rate_pps > 0 else 0
            pct = done * 100 // total
            print(f"\r  [{pct:3d}%] {done}/{total} packets  ~{eta:.0f}s remaining",
                  end="", flush=True)

        mpc.upload_sample(pcm, rate, slot=0, progress=progress)
        elapsed = time.time() - start
        print(f"\n  Done in {elapsed:.1f}s")

    except MPC2000XLError as e:
        print(f"\n  Upload failed: {e}")
        return 1
    finally:
        mpc.close()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Akai MPC2000XL sample upload via MIDI SDS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ports
  %(prog)s upload kick.wav
  %(prog)s upload kick.wav --in "Volt 2" --out "Volt 2"
""",
    )
    subparsers = parser.add_subparsers(dest="command")

    def add_port_args(sub):
        sub.add_argument("--in", dest="input_port", default=None)
        sub.add_argument("--out", dest="output_port", default=None)

    sub_ports = subparsers.add_parser("ports", help="List MIDI ports")
    sub_ports.set_defaults(func=cmd_ports)
    add_port_args(sub_ports)

    sub_upload = subparsers.add_parser("upload", help="Upload WAV to MPC")
    sub_upload.add_argument("wav_file", help="WAV file to upload")
    add_port_args(sub_upload)
    sub_upload.set_defaults(func=cmd_upload)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
