"""Kit manifest: the JSON sidecar that describes a sliced break.

A manifest (`<name>.rcy.json`) sits next to the rendered slice WAVs and
records where each slice lives in the source WAV, which MIDI key it maps
to and which file it was rendered to. Slice `start`/`end` are sample
offsets into `source`; `end` is exclusive. `source` is relative to the
manifest's directory unless absolute.

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

    def to_dict(self) -> dict[str, Any]:
        return {
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

        manifest = cls(
            source=_require_str(data, "source"),
            sample_rate=_require_int(data, "sample_rate"),
            channels=_require_int(data, "channels"),
            bpm=_require_number(data, "bpm"),
            measures=_require_int(data, "measures"),
            region=(_require_int(region, "start"), _require_int(region, "end")),
            boundaries=[int(b) for b in boundaries],
            slices=[_slice_from_dict(s) for s in slices_raw],
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
        if not self.slices:
            raise ManifestError("slices must not be empty")
        cut_points = set(self.boundaries)
        seen_files: set[str] = set()
        for position, s in enumerate(self.slices, start=1):
            if s.index != position:
                raise ManifestError(
                    f"slice at position {position} has index {s.index}; "
                    "indices are 1-based and sequential"
                )
            if s.start < start or s.end > end or s.start >= s.end:
                raise ManifestError(
                    f"slice {s.index} range [{s.start}, {s.end}) is outside "
                    f"region {self.region} or empty"
                )
            if s.start not in cut_points or s.end not in cut_points:
                raise ManifestError(
                    f"slice {s.index} edges {s.start}/{s.end} must both appear in boundaries"
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
    total_samples: int, sample_rate: int, measures: int, resolution: int
) -> list[int]:
    """Cut points for `measures` x `resolution` equal divisions over the whole file.

    Mirrors SegmentManager.split_by_measures arithmetic (times in seconds,
    truncated to samples) so headless and TUI exports produce identical cuts.
    """
    if measures < 1 or resolution < 1:
        raise ValueError("measures and resolution must be positive")
    total_time = total_samples / sample_rate
    total_divisions = measures * resolution
    time_per_division = total_time / total_divisions
    boundaries = [0]
    for i in range(1, total_divisions):
        boundaries.append(int((i * time_per_division) * sample_rate))
    boundaries.append(int(total_time * sample_rate))
    return boundaries


def slices_from_boundaries(boundaries: list[int], first_key: int = FIRST_KEY) -> list[Slice]:
    """One slice per adjacent boundary pair, keys chromatic from `first_key`."""
    return [
        Slice(index=i + 1, start=start, end=end, key=first_key + i, file=f"{i + 1:03d}.wav")
        for i, (start, end) in enumerate(pairwise(boundaries))
    ]


def build_manifest(audio: SourceAudio, measures: int, resolution: int) -> KitManifest:
    """Manifest for equal divisions of the whole file; `source` is the absolute path."""
    boundaries = measure_boundaries(audio.total_samples, audio.sample_rate, measures, resolution)
    return KitManifest(
        source=audio.path,
        sample_rate=audio.sample_rate,
        channels=audio.channels,
        bpm=bpm_from_measures(audio.total_samples, audio.sample_rate, measures),
        measures=measures,
        region=(boundaries[0], boundaries[-1]),
        boundaries=boundaries,
        slices=slices_from_boundaries(boundaries),
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


def _slice_from_dict(data: Any) -> Slice:
    if not isinstance(data, dict):
        raise ManifestError("each slice must be a JSON object")
    role = data.get("role", "")
    if not isinstance(role, str):
        raise ManifestError(f"slice role must be a string, got {role!r}")
    return Slice(
        index=_require_int(data, "index"),
        start=_require_int(data, "start"),
        end=_require_int(data, "end"),
        key=_require_int(data, "key"),
        file=_require_str(data, "file"),
        role=role,
    )
