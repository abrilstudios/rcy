"""Kit manifest: the JSON sidecar that describes a sliced break.

A manifest (`<name>.rcy.json`) sits next to the rendered slice WAVs and
records where each slice lives in the source WAV, which MIDI key it maps
to and which file it was rendered to. `boundaries` is the authoritative
list of cut points (sample offsets into `source`); slice i spans
`boundaries[i-1]` to `boundaries[i]`, end exclusive. Each slice's
`start`/`end` are written for readability and ignored on load. `source`
is relative to the manifest's directory unless absolute. `onsets`, when
present, lists detected transients (samples) for snapping and reporting;
`grid_offset` (samples, default 0) is where the bar grid starts. Neither
affects slicing.

This module has no UI or audio-device dependencies. `load_source_audio`
reads a WAV with soundfile, and `load_kit` returns a manifest plus the
decoded source so slices can be re-rendered headlessly.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field, replace
from itertools import pairwise
from typing import Any

import numpy as np
import soundfile as sf

from custom_types import AudioArray

SCHEMA_VERSION = 1
MANIFEST_SUFFIX = ".rcy.json"
FIRST_KEY = 60  # C3; slices are mapped chromatically upward from here
REQUIRED_SAMPLE_RATE = 44100


class ManifestError(ValueError):
    """Raised when a manifest is malformed or inconsistent with its source."""


@dataclass(frozen=True)
class Slice:
    index: int
    start: int
    end: int
    key: int
    file: str
    role: str = ""


@dataclass(frozen=True)
class KitManifest:
    source: str
    sample_rate: int
    channels: int
    bpm: float
    measures: int
    region: tuple[int, int]
    boundaries: list[int]
    slices: list[Slice] = field(default_factory=list)
    onsets: list[int] = field(default_factory=list)
    grid_offset: int = 0

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "rcy": SCHEMA_VERSION,
            "source": self.source,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bpm": self.bpm,
            "measures": self.measures,
            "region": {"start": self.region[0], "end": self.region[1]},
            "boundaries": list(self.boundaries),
            "slices": [asdict(s) for s in self.slices],
        }
        if self.grid_offset:
            data["grid_offset"] = self.grid_offset
        if self.onsets:
            data["onsets"] = list(self.onsets)
        return data

    @classmethod
    def from_dict(cls, data: Any) -> KitManifest:
        """Build a manifest from parsed JSON, raising ManifestError on any defect."""
        if not isinstance(data, dict):
            raise ManifestError("manifest must be a JSON object")
        version = data.get("rcy")
        if version != SCHEMA_VERSION:
            raise ManifestError(
                f"unsupported manifest version {version!r}, expected {SCHEMA_VERSION}"
            )

        region = data.get("region")
        if not isinstance(region, dict):
            raise ManifestError("region must be an object with start and end")
        slices_raw = data.get("slices")
        if not isinstance(slices_raw, list):
            raise ManifestError("slices must be a list")
        boundaries = data.get("boundaries")
        if not isinstance(boundaries, list) or not all(_is_int(b) for b in boundaries):
            raise ManifestError("boundaries must be a list of integers")

        onsets = data.get("onsets", [])
        if not isinstance(onsets, list) or not all(_is_int(o) for o in onsets):
            raise ManifestError("onsets must be a list of integers")
        grid_offset = data.get("grid_offset", 0)
        if not _is_int(grid_offset):
            raise ManifestError(f"grid_offset must be an integer, got {grid_offset!r}")

        cut_points = [int(b) for b in boundaries]
        if len(slices_raw) != len(cut_points) - 1:
            raise ManifestError(
                f"{len(cut_points)} boundaries define {len(cut_points) - 1} slices, "
                f"but {len(slices_raw)} slices are listed"
            )
        manifest = cls(
            source=_require_str(data, "source"),
            sample_rate=_require_int(data, "sample_rate"),
            channels=_require_int(data, "channels"),
            bpm=_require_number(data, "bpm"),
            measures=_require_int(data, "measures"),
            region=(_require_int(region, "start"), _require_int(region, "end")),
            boundaries=cut_points,
            slices=[
                _slice_from_dict(raw, start, end)
                for raw, (start, end) in zip(slices_raw, pairwise(cut_points), strict=True)
            ],
            onsets=[int(o) for o in onsets],
            grid_offset=int(grid_offset),
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        """Check internal consistency; raise ManifestError on the first defect."""
        if not self.source:
            raise ManifestError("source must be a non-empty path")
        if self.sample_rate <= 0:
            raise ManifestError(f"sample_rate must be positive, got {self.sample_rate}")
        if self.channels not in (1, 2):
            raise ManifestError(f"channels must be 1 or 2, got {self.channels}")
        if not math.isfinite(self.bpm) or self.bpm <= 0:
            raise ManifestError(f"bpm must be a positive number, got {self.bpm}")
        if self.measures < 1:
            raise ManifestError(f"measures must be >= 1, got {self.measures}")
        start, end = self.region
        if start < 0 or end <= start:
            raise ManifestError(f"region must satisfy 0 <= start < end, got {self.region}")
        if len(self.boundaries) < 2:
            raise ManifestError("boundaries must hold at least the region start and end")
        if any(b >= c for b, c in pairwise(self.boundaries)):
            raise ManifestError("boundaries must be strictly increasing")
        if self.boundaries[0] != start or self.boundaries[-1] != end:
            raise ManifestError(
                f"boundaries must run from region start {start} to region end {end}, "
                f"got {self.boundaries[0]}..{self.boundaries[-1]}"
            )
        if len(self.slices) != len(self.boundaries) - 1:
            raise ManifestError(
                f"{len(self.boundaries)} boundaries define {len(self.boundaries) - 1} slices, "
                f"but {len(self.slices)} slices are listed"
            )
        if any(o < 0 for o in self.onsets) or any(a >= b for a, b in pairwise(self.onsets)):
            raise ManifestError("onsets must be non-negative and strictly increasing")
        if self.grid_offset < 0:
            raise ManifestError(f"grid_offset must be >= 0, got {self.grid_offset}")
        seen_files: set[str] = set()
        for position, s in enumerate(self.slices, start=1):
            if s.index != position:
                raise ManifestError(
                    f"slice at position {position} has index {s.index}; "
                    "indices are 1-based and sequential"
                )
            expected = (self.boundaries[position - 1], self.boundaries[position])
            if (s.start, s.end) != expected:
                raise ManifestError(
                    f"slice {s.index} spans {s.start}..{s.end} but boundaries give "
                    f"{expected[0]}..{expected[1]}"
                )
            if not 0 <= s.key <= 127:
                raise ManifestError(f"slice {s.index} key {s.key} is not a MIDI note (0..127)")
            if not s.file:
                raise ManifestError(f"slice {s.index} has an empty file name")
            if s.file in seen_files:
                raise ManifestError(f"slice file {s.file!r} is used by more than one slice")
            seen_files.add(s.file)

    def save(self, path: str) -> None:
        self.validate()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
            fh.write("\n")

    @classmethod
    def load(cls, path: str) -> KitManifest:
        with open(path, encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ManifestError(f"{path}: invalid JSON: {exc}") from exc
        return cls.from_dict(data)

    def with_boundaries(self, boundaries: list[int]) -> KitManifest:
        """Copy with the same slices (keys, files, roles) over new cut points."""
        if len(boundaries) != len(self.boundaries):
            raise ManifestError(
                f"{len(boundaries)} boundaries given for {len(self.slices)} slices"
            )
        slices = [
            replace(s, start=start, end=end)
            for s, (start, end) in zip(self.slices, pairwise(boundaries), strict=True)
        ]
        return replace(
            self, region=(boundaries[0], boundaries[-1]), boundaries=list(boundaries),
            slices=slices,
        )

    def source_path(self, manifest_path: str) -> str:
        """Absolute path of the source WAV, resolving `source` against the manifest's directory."""
        if os.path.isabs(self.source):
            return self.source
        base = os.path.dirname(os.path.abspath(manifest_path))
        return os.path.normpath(os.path.join(base, self.source))

    def rebased(self, source_abs: str, directory: str) -> KitManifest:
        """Copy with `source` rewritten relative to `directory` (posix separators).

        The path stays absolute when the two share no ancestor below the
        filesystem root, so a manifest never holds a chain of `../`.
        """
        common = os.path.commonpath([os.path.abspath(source_abs), os.path.abspath(directory)])
        if os.path.dirname(common) == common:
            return replace(self, source=os.path.abspath(source_abs))
        rel = os.path.relpath(source_abs, directory)
        return replace(self, source=rel.replace(os.sep, "/"))


@dataclass(frozen=True)
class SourceAudio:
    """A decoded WAV: mono files are duplicated into both channels."""

    path: str
    sample_rate: int
    channels: int
    data_left: AudioArray
    data_right: AudioArray

    @property
    def is_stereo(self) -> bool:
        return self.channels > 1

    @property
    def total_samples(self) -> int:
        return len(self.data_left)

    @property
    def total_time(self) -> float:
        return self.total_samples / self.sample_rate


def load_source_audio(path: str) -> SourceAudio:
    """Read a WAV with soundfile. No audio device is touched."""
    path = os.path.abspath(path)
    audio, sample_rate = sf.read(path, always_2d=True)
    if sample_rate != REQUIRED_SAMPLE_RATE:
        raise ValueError(
            f"Unsupported sample rate: {sample_rate} Hz. "
            f"RCY requires {REQUIRED_SAMPLE_RATE} Hz audio files."
        )
    channels = audio.shape[1]
    if channels > 1:
        data_left = np.ascontiguousarray(audio[:, 0])
        data_right = np.ascontiguousarray(audio[:, 1])
    else:
        data_left = audio[:, 0].copy()
        data_right = data_left.copy()
    return SourceAudio(
        path=path,
        sample_rate=sample_rate,
        channels=2 if channels > 1 else 1,
        data_left=data_left,
        data_right=data_right,
    )


def bpm_from_measures(total_samples: int, sample_rate: int, measures: int) -> float:
    """Tempo implied by a loop of `measures` bars of 4/4 lasting `total_samples`."""
    if total_samples <= 0 or measures < 1:
        raise ValueError(f"need positive samples and measures, got {total_samples}, {measures}")
    duration = total_samples / sample_rate
    return (60.0 * measures * 4) / duration


def measure_boundaries(
    total_samples: int, sample_rate: int, measures: int, resolution: int, grid_offset: int = 0
) -> list[int]:
    """Cut points for `measures` x `resolution` equal divisions over the whole file.

    Mirrors SegmentManager.split_by_measures arithmetic (times in seconds,
    truncated to samples) so headless and TUI exports produce identical cuts.
    `grid_offset` shifts every interior cut by that many samples; the first
    and last cuts stay at 0 and the end of the file.
    """
    if measures < 1 or resolution < 1:
        raise ValueError("measures and resolution must be positive")
    total_time = total_samples / sample_rate
    total_divisions = measures * resolution
    time_per_division = total_time / total_divisions
    boundaries = [0]
    for i in range(1, total_divisions):
        boundaries.append(int((i * time_per_division) * sample_rate) + grid_offset)
    boundaries.append(int(total_time * sample_rate))
    if any(a >= b for a, b in pairwise(boundaries)):
        raise ValueError(
            f"grid offset {grid_offset} pushes a cut past its neighbour or the end of the file"
        )
    return boundaries


def slices_from_boundaries(
    boundaries: list[int], first_key: int = FIRST_KEY, roles: list[str] | None = None
) -> list[Slice]:
    """One slice per adjacent boundary pair, keys chromatic from `first_key`.

    `roles`, when given, has one entry per slice.
    """
    count = len(boundaries) - 1
    if roles is None:
        roles = [""] * count
    if len(roles) != count:
        raise ValueError(f"{count} slices but {len(roles)} roles")
    return [
        Slice(index=i + 1, start=start, end=end, key=first_key + i, file=f"{i + 1:03d}.wav",
              role=role)
        for i, ((start, end), role) in enumerate(zip(pairwise(boundaries), roles, strict=True))
    ]


def build_manifest(
    audio: SourceAudio, measures: int, resolution: int, grid_offset: int = 0
) -> KitManifest:
    """Manifest for equal divisions of the whole file; `source` is the absolute path."""
    boundaries = measure_boundaries(
        audio.total_samples, audio.sample_rate, measures, resolution, grid_offset
    )
    return manifest_from_boundaries(audio, measures, boundaries, grid_offset=grid_offset)


def manifest_from_boundaries(
    audio: SourceAudio,
    measures: int,
    boundaries: list[int],
    roles: list[str] | None = None,
    grid_offset: int = 0,
    onsets: list[int] | None = None,
) -> KitManifest:
    """Manifest for explicit cut points over the whole file; `source` is the absolute path.

    `boundaries` must start at 0 and end at the last sample of `audio`.
    """
    return KitManifest(
        source=audio.path,
        sample_rate=audio.sample_rate,
        channels=audio.channels,
        bpm=bpm_from_measures(audio.total_samples, audio.sample_rate, measures),
        measures=measures,
        region=(boundaries[0], boundaries[-1]),
        boundaries=list(boundaries),
        slices=slices_from_boundaries(boundaries, roles=roles),
        onsets=[] if onsets is None else list(onsets),
        grid_offset=grid_offset,
    )


def load_kit(manifest_path: str) -> tuple[KitManifest, SourceAudio]:
    """Load a manifest and its source WAV, checking the two agree."""
    manifest = KitManifest.load(manifest_path)
    audio = load_source_audio(manifest.source_path(manifest_path))
    if audio.sample_rate != manifest.sample_rate:
        raise ManifestError(
            f"manifest sample_rate {manifest.sample_rate} != source {audio.sample_rate} "
            f"({audio.path})"
        )
    if audio.channels != manifest.channels:
        raise ManifestError(
            f"manifest channels {manifest.channels} != source {audio.channels} ({audio.path})"
        )
    if manifest.region[1] > audio.total_samples:
        raise ManifestError(
            f"region end {manifest.region[1]} exceeds source length {audio.total_samples} "
            f"({audio.path})"
        )
    return manifest, audio


def manifest_path_for(directory: str) -> str:
    """`<dir>/<basename of dir>.rcy.json`, the manifest an export writes."""
    return os.path.join(directory, export_stem(directory) + MANIFEST_SUFFIX)


def export_stem(directory: str) -> str:
    """Base name shared by the SFZ, MIDI and manifest files in `directory`."""
    stem = os.path.basename(os.path.normpath(directory))
    if not stem or stem == os.path.sep:
        return "instrument"
    return stem


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not _is_int(value):
        raise ManifestError(f"{key} must be an integer, got {value!r}")
    return int(value)


def _require_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{key} must be a number, got {value!r}")
    return float(value)


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ManifestError(f"{key} must be a string, got {value!r}")
    return value


def _slice_from_dict(data: Any, start: int, end: int) -> Slice:
    """Slice from JSON; `start`/`end` come from boundaries, any authored values are ignored."""
    if not isinstance(data, dict):
        raise ManifestError("each slice must be a JSON object")
    role = data.get("role", "")
    if not isinstance(role, str):
        raise ManifestError(f"slice role must be a string, got {role!r}")
    return Slice(
        index=_require_int(data, "index"),
        start=start,
        end=end,
        key=_require_int(data, "key"),
        file=_require_str(data, "file"),
        role=role,
    )
