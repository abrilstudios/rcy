"""Cut lists: text files of cut positions with roles, snapping, and the slice table.

A cut list has one cut per line: a position, then an optional role that
runs to the end of the line. Positions are samples (`19388`), seconds
(`0.44s`) or beats (`2.3` or `2.3.1`, bar.beat.sixteenth, 1-based); see
`BeatGrid.parse_position`. Blank lines and lines starting with `#` are
skipped. A cut at 0 is implied when the first cut is later; the end of the
file is always the last boundary.

    1.1     b1 kicks
    1.2     b1 snare cell
    1.3.3   b1 turnaround
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from beat_grid import BeatGrid
from kit_manifest import KitManifest
from onsets import nearest_onset


@dataclass(frozen=True)
class Cut:
    sample: int
    role: str = ""


def parse_cut_list(text: str, grid: BeatGrid) -> list[Cut]:
    """Cuts from cut-list text, in file order. Raises ValueError with the line number."""
    cuts: list[Cut] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        position, _, role = line.partition(" ")
        try:
            sample = grid.parse_position(position)
        except ValueError as exc:
            raise ValueError(f"cuts line {lineno}: {exc}") from exc
        cuts.append(Cut(sample=sample, role=role.strip()))
    if not cuts:
        raise ValueError("cut list has no cuts")
    return cuts


def boundaries_from_cuts(cuts: list[Cut], total_samples: int) -> tuple[list[int], list[str]]:
    """Boundaries `[0, ..., total_samples]` and one role per slice from a cut list.

    Cuts must be strictly increasing and inside the file. A leading cut at
    0 is added when missing, with an empty role.
    """
    if cuts[0].sample != 0:
        cuts = [Cut(0), *cuts]
    for a, b in pairwise(cuts):
        if b.sample <= a.sample:
            raise ValueError(f"cuts must increase: {b.sample} follows {a.sample}")
    if cuts[-1].sample >= total_samples:
        raise ValueError(
            f"cut at {cuts[-1].sample} is at or past the end of the file ({total_samples} samples)"
        )
    boundaries = [c.sample for c in cuts] + [total_samples]
    roles = [c.role for c in cuts]
    return boundaries, roles


def snap_to_onsets(
    boundaries: list[int], onsets: list[int], grid: BeatGrid, pre_ms: float
) -> tuple[list[int], list[str]]:
    """Move each interior cut to `pre_ms` before its nearest onset.

    A cut moves only when an onset lies within half a sixteenth of it;
    otherwise it stays and a warning names it. The first and last
    boundaries never move. Raises ValueError if snapping makes the
    boundaries stop increasing.
    """
    pre = round(pre_ms * grid.sample_rate / 1000.0)
    window = grid.samples_per_sixteenth / 2
    snapped = [boundaries[0]]
    warnings: list[str] = []
    for cut in boundaries[1:-1]:
        onset = nearest_onset(cut, onsets)
        if onset is None or abs(onset - cut) > window:
            warnings.append(
                f"cut at {cut} ({grid.label(cut)}): no onset within half a sixteenth, left as is"
            )
            snapped.append(cut)
        else:
            snapped.append(max(boundaries[0] + 1, onset - pre))
    snapped.append(boundaries[-1])
    if any(a >= b for a, b in pairwise(snapped)):
        raise ValueError("snapping to onsets made two cuts meet or cross; move the cuts apart")
    return snapped, warnings


def ms_to_nearest_onset(sample: int, onsets: list[int], sample_rate: int) -> float | None:
    """Signed ms from `sample` to the nearest onset (positive = onset is later)."""
    onset = nearest_onset(sample, onsets)
    if onset is None:
        return None
    return (onset - sample) * 1000.0 / sample_rate


def slice_rows(manifest: KitManifest) -> list[dict[str, Any]]:
    """One row per slice for the export table and `--json`.

    Keys: index, key, role, start, beat (nearest sixteenth, bar.beat.sixteenth),
    grid_ms (signed distance from that sixteenth), length_samples,
    length_sixteenths, and onset_ms (signed distance to the nearest onset,
    None when the manifest has no onsets).
    """
    grid = BeatGrid(manifest.sample_rate, manifest.bpm, manifest.grid_offset)
    rows = []
    for s in manifest.slices:
        rows.append({
            "index": s.index,
            "key": s.key,
            "role": s.role,
            "start": s.start,
            "beat": grid.label(s.start),
            "grid_ms": round(grid.distance_to_sixteenth_ms(s.start), 1),
            "length_samples": s.end - s.start,
            "length_sixteenths": round(grid.sixteenths(s.end - s.start), 2),
            "onset_ms": _rounded(
                ms_to_nearest_onset(s.start, manifest.onsets, manifest.sample_rate)
            ),
        })
    return rows


def onset_rows(onsets: list[int], grid: BeatGrid) -> list[dict[str, Any]]:
    """One row per onset: index, sample, seconds, beat, grid_ms."""
    return [
        {
            "index": i,
            "sample": onset,
            "seconds": round(onset / grid.sample_rate, 4),
            "beat": grid.label(onset),
            "grid_ms": round(grid.distance_to_sixteenth_ms(onset), 1),
        }
        for i, onset in enumerate(onsets, start=1)
    ]


def format_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    """Fixed-width text table; `columns` pairs a row key with its heading."""
    cells = [
        [("" if row[key] is None else str(row[key])) for key, _ in columns] for row in rows
    ]
    widths = [
        max(len(heading), *(len(line[i]) for line in cells)) if cells else len(heading)
        for i, (_, heading) in enumerate(columns)
    ]
    lines = ["  ".join(heading.ljust(w) for (_, heading), w in zip(columns, widths, strict=True))]
    for line in cells:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(line, widths, strict=True)))
    return "\n".join(line.rstrip() for line in lines)


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 1)
