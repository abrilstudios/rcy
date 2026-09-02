"""Headless slice-and-export CLI.

Slices a preset or a 44.1 kHz WAV into equal divisions and writes the
slices, an SFZ instrument, a MIDI sequence and a kit manifest to a directory:

    rcy-export --preset apache_break --out /tmp/apache
    rcy-export --input break.wav --measures 2 --resolution 4 --out /tmp/break
    rcy-export --from-manifest /tmp/apache/apache.rcy.json

Output layout (for --out DIR):
    DIR/001.wav, DIR/002.wav, ...   one file per slice
    DIR/<basename of DIR>.sfz       regions mapped chromatically from C3
    DIR/<basename of DIR>.mid       one note per slice at the source tempo
    DIR/<basename of DIR>.rcy.json  kit manifest (source, tempo, slice offsets, keys)

--from-manifest re-renders from an edited manifest; --out defaults to the
manifest's own directory so the files are rewritten in place. No audio
device is opened.
"""

import argparse
import os
import pathlib
import sys

from config_manager import config
from export_utils import export_kit
from kit_manifest import ManifestError, build_manifest, load_kit, load_source_audio
from logging_config import setup_logging
from sfz_writers import SFZ_DIALECTS

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcy-export",
        description="Slice a break into equal divisions; export WAV slices, SFZ, MIDI, manifest.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--preset", "-p", help="Preset id from config/presets (e.g. apache_break)")
    source.add_argument("--input", "-i", help="Path to a 44100 Hz WAV file")
    source.add_argument(
        "--from-manifest", "-f", metavar="KIT.rcy.json",
        help="Re-render slices, SFZ and MIDI from an existing kit manifest",
    )
    parser.add_argument(
        "--out", "-o",
        help="Output directory (created if missing). Required unless --from-manifest, "
             "where it defaults to the manifest's directory.",
    )
    parser.add_argument(
        "--measures", "-m", type=int,
        help="Number of 4/4 measures in the loop. Required with --input; "
             "defaults to the preset's value with --preset.",
    )
    parser.add_argument(
        "--resolution", "-r", type=int, default=4,
        help="Slices per measure (default: 4)",
    )
    parser.add_argument(
        "--sfz-dialect", choices=SFZ_DIALECTS, default="files",
        help="files: one region per slice WAV (default). "
             "offsets: regions with start=/end= sample offsets into the source WAV.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()

    if args.from_manifest:
        if not os.path.isfile(args.from_manifest):
            print(f"error: manifest not found: {args.from_manifest}", file=sys.stderr)
            return 2
        try:
            manifest, audio = load_kit(args.from_manifest)
        except (ManifestError, OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        manifest_abs = os.path.abspath(args.from_manifest)
        out_dir = os.path.abspath(args.out) if args.out else os.path.dirname(manifest_abs)
        measures = manifest.measures
        resolution = len(manifest.slices) / measures
    else:
        if not args.out:
            print("error: --out is required with --preset or --input", file=sys.stderr)
            return 2
        if args.input:
            if args.measures is None:
                print("error: --measures is required with --input", file=sys.stderr)
                return 2
            if not os.path.isfile(args.input):
                print(f"error: input file not found: {args.input}", file=sys.stderr)
                return 2
            wav_path = os.path.abspath(args.input)
            measures = args.measures
        else:
            preset = config.get_preset_info(args.preset)
            if not preset:
                print(f"error: preset '{args.preset}' not found", file=sys.stderr)
                return 2
            wav_path = preset["filepath"]
            if not os.path.isabs(wav_path):
                wav_path = str(PROJECT_ROOT / wav_path)
            measures = args.measures if args.measures is not None else preset.get("measures")
            if measures is None:
                print(f"error: preset '{args.preset}' has no measures; pass --measures",
                      file=sys.stderr)
                return 2
        if measures < 1 or args.resolution < 1:
            print("error: --measures and --resolution must be positive", file=sys.stderr)
            return 2
        try:
            audio = load_source_audio(wav_path)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        manifest = build_manifest(audio, measures, args.resolution)
        out_dir = os.path.abspath(args.out)
        resolution = args.resolution

    os.makedirs(out_dir, exist_ok=True)
    stats = export_kit(manifest, audio, out_dir, sfz_dialect=args.sfz_dialect)

    print(f"source: {audio.path}")
    print(f"tempo: {stats['tempo']:.2f} BPM ({measures} measures x {resolution:g})")
    print(f"slices: {stats['segment_count']}")
    print(f"sfz: {stats['sfz_path']} ({args.sfz_dialect})")
    print(f"midi: {stats['midi_path']}")
    print(f"manifest: {stats['manifest_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
