"""Print the detected onsets of a break with their beat positions.

    rcy-onsets --preset amen_classic
    rcy-onsets --input break.wav --measures 2 --json

Each onset is listed with its sample offset, seconds, the nearest sixteenth
as bar.beat.sixteenth (1-based) and the signed distance in ms from that
sixteenth (positive means the onset is late). The same detector and
settings feed `rcy-export --onsets` and `--snap-onsets`.
"""

from __future__ import annotations

import argparse
import json
import sys

from beat_grid import BeatGrid
from cut_list import format_table, onset_rows
from kit_manifest import bpm_from_measures
from logging_config import setup_headless_logging
from onsets import detect_onsets_precise
from utils.source_args import (
    CliError,
    add_measures_argument,
    add_source_arguments,
    load_source,
    ms_to_samples,
)

ONSET_COLUMNS = [
    ("index", "#"),
    ("sample", "sample"),
    ("seconds", "seconds"),
    ("beat", "beat"),
    ("grid_ms", "grid_ms"),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcy-onsets",
        description="Detect onsets in a break and print them with beat positions.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    add_source_arguments(source)
    add_measures_argument(parser)
    parser.add_argument(
        "--grid-offset", type=float, default=0.0, metavar="MS",
        help="Start the bar grid this many ms into the file (default: 0)",
    )
    parser.add_argument("--json", action="store_true", help="Print one JSON document instead")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_headless_logging()
    try:
        audio, measures = load_source(args.preset, args.input, args.measures)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    bpm = bpm_from_measures(audio.total_samples, audio.sample_rate, measures)
    grid = BeatGrid(audio.sample_rate, bpm, ms_to_samples(args.grid_offset, audio.sample_rate))
    onsets = detect_onsets_precise(audio.data_left, audio.sample_rate)
    rows = onset_rows(onsets, grid)

    if args.json:
        print(json.dumps({
            "source": audio.path,
            "sample_rate": audio.sample_rate,
            "bpm": bpm,
            "measures": measures,
            "grid_offset": grid.offset,
            "samples_per_sixteenth": grid.samples_per_sixteenth,
            "onsets": rows,
        }, indent=2))
        return 0

    print(f"source: {audio.path}")
    print(f"tempo: {bpm:.2f} BPM, {measures} measures, "
          f"sixteenth = {grid.samples_per_sixteenth:.1f} samples "
          f"({grid.samples_per_sixteenth * 1000 / audio.sample_rate:.1f} ms)")
    print(f"onsets: {len(rows)}")
    if rows:
        print(format_table(rows, ONSET_COLUMNS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
