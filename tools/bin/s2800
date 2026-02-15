#!/usr/bin/env python3
"""Akai S2800 sampler CLI.

Upload samples and manage the S2800 over MIDI.

Usage:
    s2800 ports                         List MIDI ports
    s2800 list                          List samples on device
    s2800 upload <wav> [--name NAME]    Upload single sample
    s2800 delete-all                    Delete all samples

Examples:
    s2800 ports
    s2800 list
    s2800 upload sounds/606/606_01_kick.wav
    s2800 upload kick.wav --in "Volt 2" --out "Volt 2"
    s2800 delete-all
"""

import argparse
import sys
import time
from pathlib import Path

# Add src/python to path for imports
src_path = Path(__file__).resolve().parent.parent.parent / "src" / "python"
sys.path.insert(0, str(src_path))

import numpy as np

try:
    import soundfile as sf
except ImportError:
    sf = None

from s2800 import S2800
from s2800.sampler import S2800Error


def load_wav(path: Path) -> tuple[bytes, int]:
    """Load WAV file, return mono 16-bit PCM data and sample rate."""
    if sf is None:
        raise RuntimeError("soundfile not installed. Run: pip install soundfile")

    data, samplerate = sf.read(str(path), dtype='float32')

    # Mix to mono if stereo
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    # Convert to 16-bit signed PCM
    clipped = np.clip(data, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16).tobytes()
    return pcm, samplerate


def cmd_ports(args):
    """List all MIDI ports."""
    inputs, outputs = S2800.list_ports()

    print("MIDI Input Ports:")
    if inputs:
        for i, name in enumerate(inputs):
            print(f"  [{i}] {name}")
    else:
        print("  (none found)")

    print()
    print("MIDI Output Ports:")
    if outputs:
        for i, name in enumerate(outputs):
            print(f"  [{i}] {name}")
    else:
        print("  (none found)")

    # Show auto-detection result
    found_in, found_out = S2800.find_ports()
    print()
    if found_in and found_out:
        print(f"Auto-detected S2800:")
        print(f"  Input:  {found_in}")
        print(f"  Output: {found_out}")
    else:
        print("S2800 not auto-detected. Use --in/--out to specify ports manually.")

    return 0


def cmd_list(args):
    """List samples on the S2800."""
    sampler = S2800(port_in=args.input_port, port_out=args.output_port)

    try:
        sampler.open()
    except S2800Error as e:
        print(f"Connection failed: {e}")
        return 1
    except Exception as e:
        print(f"Failed to open MIDI ports: {e}")
        return 1

    try:
        samples = sampler.list_samples()
        if samples:
            print(f"Samples ({len(samples)}):")
            for i, name in enumerate(samples):
                print(f"  [{i:2d}] {name}")
        else:
            print("No samples in memory")
    finally:
        sampler.close()

    return 0


def cmd_upload(args):
    """Upload a single WAV file."""
    wav_path = Path(args.wav_file)

    if not wav_path.exists():
        print(f"File not found: {wav_path}")
        return 1

    if wav_path.suffix.lower() != '.wav':
        print(f"Not a WAV file: {wav_path}")
        return 1

    print(f"Loading {wav_path.name}...")
    try:
        pcm_data, sample_rate = load_wav(wav_path)
    except Exception as e:
        print(f"Failed to load audio: {e}")
        return 1

    sample_count = len(pcm_data) // 2
    duration = sample_count / sample_rate
    sample_name = args.name or wav_path.stem[:12].upper()

    print(f"  {sample_rate}Hz, {duration:.2f}s, {sample_count} samples")
    print(f"  Name: \"{sample_name}\"")

    sds_bytes = sample_count * 3
    packets = (sds_bytes + 119) // 120
    est_seconds = (packets * 127) / 3100
    print(f"  Estimated: {packets} packets, ~{est_seconds:.0f}s")

    sampler = S2800(port_in=args.input_port, port_out=args.output_port)

    try:
        sampler.open()
    except S2800Error as e:
        print(f"Connection failed: {e}")
        return 1
    except Exception as e:
        print(f"Failed to open MIDI ports: {e}")
        return 1

    try:
        start_time = time.time()

        def progress(pkt, total):
            elapsed = time.time() - start_time
            rate = pkt / elapsed if elapsed > 0 else 0
            eta = (total - pkt) / rate if rate > 0 else 0
            pct = pkt * 100 // total
            print(f"\r  [{pct:3d}%] {pkt}/{total} packets, {elapsed:.0f}s elapsed, ~{eta:.0f}s remaining", end="", flush=True)

        idx = sampler.upload_sample(
            pcm_data=pcm_data,
            sample_rate=sample_rate,
            name=sample_name,
            progress=progress,
        )

        elapsed = time.time() - start_time
        print(f"\n  Upload complete in {elapsed:.1f}s (slot {idx})")

        # Verify
        print("  Verifying...", end=" ", flush=True)
        time.sleep(0.3)
        names = sampler.list_samples()
        print(f"{len(names)} samples")
        for i, name in enumerate(names):
            marker = " <-- NEW" if i == idx else ""
            print(f"    [{i}] {name}{marker}")

    except S2800Error as e:
        print(f"\n  Upload failed: {e}")
        return 1
    finally:
        sampler.close()

    return 0


def cmd_delete_all(args):
    """Delete all samples."""
    sampler = S2800(port_in=args.input_port, port_out=args.output_port)

    try:
        sampler.open()
    except S2800Error as e:
        print(f"Connection failed: {e}")
        return 1
    except Exception as e:
        print(f"Failed to open MIDI ports: {e}")
        return 1

    try:
        samples = sampler.list_samples()
        if not samples:
            print("No samples to delete")
            return 0

        print(f"Deleting {len(samples)} samples...")
        sampler.delete_all_samples()

        time.sleep(0.5)
        remaining = sampler.list_samples()
        print(f"  Done. {len(remaining)} samples remaining.")
    finally:
        sampler.close()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Akai S2800 sampler CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ports
  %(prog)s list
  %(prog)s upload kick.wav
  %(prog)s upload kick.wav --in "Volt 2" --out "Volt 2"
  %(prog)s delete-all
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    def add_port_args(sub):
        sub.add_argument("--in", dest="input_port", default=None,
                         help="MIDI input port name (auto-detected if omitted)")
        sub.add_argument("--out", dest="output_port", default=None,
                         help="MIDI output port name (auto-detected if omitted)")

    # ports
    sub_ports = subparsers.add_parser("ports", help="List MIDI ports")
    sub_ports.set_defaults(func=cmd_ports)

    # list
    sub_list = subparsers.add_parser("list", help="List samples on device")
    add_port_args(sub_list)
    sub_list.set_defaults(func=cmd_list)

    # upload
    sub_upload = subparsers.add_parser("upload", help="Upload single WAV file")
    sub_upload.add_argument("wav_file", help="WAV file to upload")
    sub_upload.add_argument("--name", type=str, default=None,
                            help="Sample name (default: filename, max 12 chars)")
    add_port_args(sub_upload)
    sub_upload.set_defaults(func=cmd_upload)

    # delete-all
    sub_delete = subparsers.add_parser("delete-all", help="Delete all samples")
    add_port_args(sub_delete)
    sub_delete.set_defaults(func=cmd_delete_all)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
