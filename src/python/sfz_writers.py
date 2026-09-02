"""SFZ text from a kit manifest, in two dialects.

`files`: one region per rendered slice WAV, `sample=001.wav key=60`.
`offsets`: one region per slice into the source WAV, `sample=amen.wav
start= end= key=` with an optional `// role` comment, the form used by
presets/*/*.sfz. SFZ `end` is the last sample played (inclusive), so it is
the manifest's exclusive `end` minus one.

Both writers are pure functions of the manifest.
"""

from __future__ import annotations

import re

from kit_manifest import Slice

SFZ_DIALECTS = ("files", "offsets")

_OFFSET_REGION = re.compile(
    r"^<region>\s+sample=(?P<sample>\S+)\s+start=(?P<start>\d+)\s+end=(?P<end>\d+)"
    r"\s+key=(?P<key>\d+)\s*(?://\s*(?P<role>.*?))?\s*$"
)


def write_sfz_files(slices: list[Slice]) -> str:
    """Files dialect: regions reference the rendered slice WAVs."""
    return "\n".join(f"<region> sample={s.file} key={s.key}" for s in slices)


def write_sfz_offsets(source: str, slices: list[Slice]) -> str:
    """Offsets dialect: regions reference sample ranges of `source`."""
    lines = []
    for s in slices:
        line = f"<region> sample={source} start={s.start} end={s.end - 1} key={s.key}"
        if s.role:
            line += f" // {s.role}"
        lines.append(line)
    return "\n".join(lines)


def write_sfz(dialect: str, source: str, slices: list[Slice]) -> str:
    if dialect == "files":
        return write_sfz_files(slices)
    if dialect == "offsets":
        return write_sfz_offsets(source, slices)
    raise ValueError(f"unknown SFZ dialect {dialect!r}; expected one of {SFZ_DIALECTS}")


def parse_sfz_offsets(text: str) -> tuple[str, list[Slice]]:
    """Read offsets-dialect regions back into slices.

    Returns the source sample path and the slices, indexed 1..N in file
    order with `file` set to the RCY slice name. Comment-only and blank
    lines are skipped; any other line raises ValueError.
    """
    source: str | None = None
    slices: list[Slice] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        match = _OFFSET_REGION.match(line)
        if match is None:
            raise ValueError(f"line {lineno}: not an offsets-dialect region: {raw!r}")
        sample = match.group("sample")
        if source is None:
            source = sample
        elif sample != source:
            raise ValueError(f"line {lineno}: sample {sample!r} differs from {source!r}")
        index = len(slices) + 1
        slices.append(
            Slice(
                index=index,
                start=int(match.group("start")),
                end=int(match.group("end")) + 1,
                key=int(match.group("key")),
                file=f"{index:03d}.wav",
                role=(match.group("role") or "").strip(),
            )
        )
    if source is None:
        raise ValueError("no <region> lines found")
    return source, slices
