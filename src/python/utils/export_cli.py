"""Headless slice-and-export CLI.

Slices a preset or a 44.1 kHz WAV into equal divisions and writes the
segments, an SFZ instrument and a MIDI sequence to a directory:

    rcy-export --preset apache_break --out /tmp/apache
    rcy-export --input break.wav --measures 2 --resolution 4 --out /tmp/break

Output layout (for --out DIR):
    DIR/001.wav, DIR/002.wav, ...   one file per slice
    DIR/<basename of DIR>.sfz       regions mapped chromatically from C3
    DIR/<basename of DIR>.mid       one note per slice at the source tempo
"""

import argparse
import os
import sys

from audio_processor import WavAudioProcessor
from config_manager import config
from export_utils import ExportUtils
from logging_config import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcy-export",
        description="Slice a break into equal divisions and export WAV slices, SFZ and MIDI.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--preset", "-p", help="Preset id from config/presets (e.g. apache_break)")
    source.add_argument("--input", "-i", help="Path to a 44100 Hz WAV file")
    parser.add_argument("--out", "-o", required=True, help="Output directory (created if missing)")
    parser.add_argument(
        "--measures", "-m", type=int,
        help="Number of 4/4 measures in the loop. Required with --input; "
             "defaults to the preset's value with --preset.",
    )
    parser.add_argument(
        "--resolution", "-r", type=int, default=4,
        help="Slices per measure (default: 4)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()

    if args.input:
        if args.measures is None:
            print("error: --measures is required with --input", file=sys.stderr)
            return 2
        if not os.path.isfile(args.input):
            print(f"error: input file not found: {args.input}", file=sys.stderr)
            return 2
        model = WavAudioProcessor()
        model.set_filename(os.path.abspath(args.input))
        measures = args.measures
    else:
        preset = config.get_preset_info(args.preset)
        if not preset:
            print(f"error: preset '{args.preset}' not found", file=sys.stderr)
            return 2
        model = WavAudioProcessor(preset_id=args.preset)
        measures = args.measures if args.measures is not None else preset.get("measures")
        if measures is None:
            print(f"error: preset '{args.preset}' has no measures; pass --measures",
                  file=sys.stderr)
            return 2

    if measures < 1 or args.resolution < 1:
        print("error: --measures and --resolution must be positive", file=sys.stderr)
        return 2

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    model.calculate_source_bpm(measures=measures)
    model.split_by_measures(measures, args.resolution)
    stats = ExportUtils.export_segments(model, model.source_bpm, measures, out_dir)
    model.audio_engine.stop()

    print(f"source: {model.filename}")
    print(f"tempo: {stats['tempo']:.2f} BPM ({measures} measures x {args.resolution})")
    print(f"slices: {stats['segment_count']}")
    print(f"sfz: {stats['sfz_path']}")
    print(f"midi: {stats['midi_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
