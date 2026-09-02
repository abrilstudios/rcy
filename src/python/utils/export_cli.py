"""Headless slice-and-export CLI.

Slices a preset or a 44.1 kHz WAV, at equal divisions or at the cuts in a
cut list, and writes the slices, an SFZ instrument, a MIDI sequence and a
kit manifest to a directory:

    rcy-export --preset apache_break --out /tmp/apache
    rcy-export --input break.wav --measures 2 --resolution 4 --out /tmp/break
    rcy-export --preset amen_classic --cuts cuts.txt --snap-onsets --out /tmp/amen
    rcy-export --from-manifest /tmp/apache/apache.rcy.json

Output layout (for --out DIR):
    DIR/001.wav, DIR/002.wav, ...   one file per slice (files dialect, or --render)
    DIR/<basename of DIR>.sfz       regions mapped chromatically from C3
    DIR/<basename of DIR>.mid       one note per slice at the source tempo
    DIR/<basename of DIR>.rcy.json  kit manifest (source, tempo, cuts, keys, roles)

Every export prints a per-slice table: index, key, role, start sample,
nearest sixteenth as bar.beat.sixteenth, signed ms from that sixteenth,
length in sixteenths, and (when onsets are known) signed ms from the cut
to the nearest onset. --json prints the same as one JSON document.

--from-manifest re-renders from an edited manifest; --out defaults to the
manifest's own directory so the files are rewritten in place. No audio
device is opened.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace

from beat_grid import BeatGrid
from cut_list import (
    boundaries_from_cuts,
    format_table,
    parse_cut_list,
    slice_rows,
    snap_to_onsets,
)
from export_utils import export_kit
from kit_manifest import (
    KitManifest,
    ManifestError,
    SourceAudio,
    build_manifest,
    load_kit,
    manifest_from_boundaries,
    measure_boundaries,
)
from logging_config import setup_headless_logging
from onsets import detect_onsets_precise
from sfz_writers import SFZ_DIALECTS
from utils.source_args import (
    CliError,
    add_measures_argument,
    add_source_arguments,
    load_source,
    ms_to_samples,
)

DEFAULT_RESOLUTION = 4
DEFAULT_SNAP_MS = 3.0

SLICE_COLUMNS = [
    ("index", "#"),
    ("key", "key"),
    ("role", "role"),
    ("start", "start"),
    ("beat", "beat"),
    ("grid_ms", "grid_ms"),
    ("length_sixteenths", "16ths"),
]
ONSET_COLUMN = ("onset_ms", "onset_ms")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcy-export",
        description="Slice a break at equal divisions or at listed cuts; "
                    "export WAV slices, SFZ, MIDI, manifest.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    add_source_arguments(source)
    source.add_argument(
        "--from-manifest", "-f", metavar="KIT.rcy.json",
        help="Re-render slices, SFZ and MIDI from an existing kit manifest",
    )
    parser.add_argument(
        "--out", "-o",
        help="Output directory (created if missing). Required unless --from-manifest, "
             "where it defaults to the manifest's directory.",
    )
    add_measures_argument(parser)
    cutting = parser.add_mutually_exclusive_group()
    cutting.add_argument(
        "--resolution", "-r", type=int,
        help=f"Slices per measure for equal chops (default: {DEFAULT_RESOLUTION})",
    )
    cutting.add_argument(
        "--cuts", metavar="CUTS",
        help="Cut list file, or - for stdin: one cut per line, a position then an optional "
             "role. Positions are samples (19388), seconds (0.44s) or beats (2.3 or 2.3.1 "
             "as bar.beat.sixteenth, 1-based). A cut at 0 is implied; the file end is "
             "always the last cut.",
    )
    parser.add_argument(
        "--onsets", action="store_true",
        help="Detect onsets, record them in the manifest and report each cut's distance "
             "to the nearest one",
    )
    parser.add_argument(
        "--snap-onsets", nargs="?", const=DEFAULT_SNAP_MS, type=float, metavar="MS",
        help=f"Move each cut to MS ms before the nearest onset (default {DEFAULT_SNAP_MS:g}) "
             "when one lies within half a sixteenth; otherwise leave it and warn. "
             "Implies --onsets.",
    )
    parser.add_argument(
        "--grid-offset", type=float, default=0.0, metavar="MS",
        help="Start the bar grid this many ms into the file, for beat positions and "
             "equal chops (default: 0)",
    )
    parser.add_argument(
        "--sfz-dialect", choices=SFZ_DIALECTS, default="files",
        help="files: one region per slice WAV (default). "
             "offsets: regions with start=/end= sample offsets into the source WAV; "
             "slice WAVs are not written unless --render is given.",
    )
    parser.add_argument(
        "--render", action="store_true",
        help="Write slice WAVs with the offsets dialect too",
    )
    parser.add_argument("--json", action="store_true", help="Print one JSON document instead")
    return parser


def read_cut_list(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    if not os.path.isfile(path):
        raise CliError(f"cuts file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def equal_resolution(manifest: KitManifest, audio: SourceAudio) -> int | None:
    """Slices per measure when the manifest is an equal chop, else None."""
    count = len(manifest.slices)
    if count % manifest.measures:
        return None
    resolution = count // manifest.measures
    try:
        expected = measure_boundaries(
            audio.total_samples, audio.sample_rate, manifest.measures, resolution,
            manifest.grid_offset,
        )
    except ValueError:
        return None
    return resolution if expected == manifest.boundaries else None


def prepare(args: argparse.Namespace) -> tuple[KitManifest, SourceAudio, str, list[str]]:
    """Build the manifest to export. Returns manifest, audio, out_dir, warnings."""
    warnings: list[str] = []
    want_onsets = args.onsets or args.snap_onsets is not None

    if args.from_manifest:
        for flag, value in (("--cuts", args.cuts), ("--measures", args.measures),
                            ("--resolution", args.resolution)):
            if value is not None:
                raise CliError(f"{flag} cannot be combined with --from-manifest")
        if args.grid_offset:
            raise CliError("--grid-offset cannot be combined with --from-manifest; "
                           "edit grid_offset in the manifest")
        if not os.path.isfile(args.from_manifest):
            raise CliError(f"manifest not found: {args.from_manifest}")
        try:
            manifest, audio = load_kit(args.from_manifest)
        except (ManifestError, OSError, ValueError) as exc:
            raise CliError(str(exc)) from exc
        manifest_abs = os.path.abspath(args.from_manifest)
        out_dir = os.path.abspath(args.out) if args.out else os.path.dirname(manifest_abs)
        if args.onsets or (want_onsets and not manifest.onsets):
            manifest = replace(manifest, onsets=detect_onsets_precise(
                audio.data_left, audio.sample_rate))
    else:
        if not args.out:
            raise CliError("--out is required with --preset or --input")
        audio, measures = load_source(args.preset, args.input, args.measures)
        grid_offset = ms_to_samples(args.grid_offset, audio.sample_rate)
        onsets = detect_onsets_precise(audio.data_left, audio.sample_rate) if want_onsets else []
        if args.cuts is not None:
            probe = build_manifest(audio, measures, 1, grid_offset)
            grid = BeatGrid(audio.sample_rate, probe.bpm, grid_offset)
            try:
                cuts = parse_cut_list(read_cut_list(args.cuts), grid)
                boundaries, roles = boundaries_from_cuts(cuts, audio.total_samples)
            except ValueError as exc:
                raise CliError(str(exc)) from exc
            manifest = manifest_from_boundaries(
                audio, measures, boundaries, roles, grid_offset=grid_offset, onsets=onsets
            )
        else:
            resolution = DEFAULT_RESOLUTION if args.resolution is None else args.resolution
            if resolution < 1:
                raise CliError("--resolution must be positive")
            try:
                manifest = build_manifest(audio, measures, resolution, grid_offset)
            except ValueError as exc:
                raise CliError(str(exc)) from exc
            manifest = replace(manifest, onsets=onsets)
        out_dir = os.path.abspath(args.out)

    if args.snap_onsets is not None:
        if args.snap_onsets < 0:
            raise CliError("--snap-onsets must be >= 0")
        grid = BeatGrid(manifest.sample_rate, manifest.bpm, manifest.grid_offset)
        try:
            snapped, warnings = snap_to_onsets(
                manifest.boundaries, manifest.onsets, grid, args.snap_onsets
            )
        except ValueError as exc:
            raise CliError(str(exc)) from exc
        manifest = manifest.with_boundaries(snapped)
    return manifest, audio, out_dir, warnings


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_headless_logging()
    try:
        manifest, audio, out_dir, warnings = prepare(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    os.makedirs(out_dir, exist_ok=True)
    render = args.sfz_dialect == "files" or args.render
    stats = export_kit(manifest, audio, out_dir, sfz_dialect=args.sfz_dialect,
                       render_slices=render)
    resolution = equal_resolution(manifest, audio)
    rows = slice_rows(manifest)

    if args.json:
        print(json.dumps({
            "source": audio.path,
            "tempo": stats["tempo"],
            "measures": manifest.measures,
            "resolution": resolution,
            "grid_offset": manifest.grid_offset,
            "slice_count": len(manifest.slices),
            "onset_count": len(manifest.onsets) if manifest.onsets else None,
            "sfz": stats["sfz_path"],
            "sfz_dialect": args.sfz_dialect,
            "midi": stats["midi_path"],
            "manifest": stats["manifest_path"],
            "rendered": render,
            "warnings": warnings,
            "slices": rows,
        }, indent=2))
        return 0

    print(f"source: {audio.path}")
    print(f"tempo: {stats['tempo']:.2f} BPM, {manifest.measures} measures")
    if resolution is None:
        print(f"slices: {len(manifest.slices)}")
    else:
        print(f"slices: {len(manifest.slices)}, {resolution} per measure")
    if manifest.onsets:
        print(f"onsets: {len(manifest.onsets)}")
    print(f"sfz: {stats['sfz_path']} ({args.sfz_dialect}"
          f"{'' if render else ', slice WAVs not written'})")
    print(f"midi: {stats['midi_path']}")
    print(f"manifest: {stats['manifest_path']}")
    columns = SLICE_COLUMNS + ([ONSET_COLUMN] if manifest.onsets else [])
    print(format_table(rows, columns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
