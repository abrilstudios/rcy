"""The bar grid of a loop: sample offsets to and from beat positions.

A beat position is written `bar.beat.sixteenth`, all 1-based, so `1.1.1`
is the first sample of the grid, `2.3` is bar 2 beat 3 (sixteenth 1) and
`1.2.3` is the "and" of beat 2 in bar 1. The grid is 4/4 at `bpm`, starting
`offset` samples into the file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BEATS_PER_BAR = 4
SIXTEENTHS_PER_BEAT = 4
SIXTEENTHS_PER_BAR = BEATS_PER_BAR * SIXTEENTHS_PER_BEAT

_BEAT_POSITION = re.compile(r"^(?P<bar>\d+)\.(?P<beat>\d+)(?:\.(?P<sixteenth>\d+))?$")


@dataclass(frozen=True)
class BeatGrid:
    sample_rate: int
    bpm: float
    offset: int = 0

    @property
    def samples_per_beat(self) -> float:
        return self.sample_rate * 60.0 / self.bpm

    @property
    def samples_per_sixteenth(self) -> float:
        return self.samples_per_beat / SIXTEENTHS_PER_BEAT

    def sample_at_sixteenth(self, index: int) -> int:
        """Sample offset of the 0-based sixteenth `index` on the grid."""
        return self.offset + round(index * self.samples_per_sixteenth)

    def sample_at(self, bar: int, beat: int, sixteenth: int = 1) -> int:
        """Sample offset of a 1-based `bar.beat.sixteenth` position."""
        if bar < 1:
            raise ValueError(f"bar must be >= 1, got {bar}")
        if not 1 <= beat <= BEATS_PER_BAR:
            raise ValueError(f"beat must be 1..{BEATS_PER_BAR}, got {beat}")
        if not 1 <= sixteenth <= SIXTEENTHS_PER_BEAT:
            raise ValueError(f"sixteenth must be 1..{SIXTEENTHS_PER_BEAT}, got {sixteenth}")
        index = (bar - 1) * SIXTEENTHS_PER_BAR + (beat - 1) * SIXTEENTHS_PER_BEAT + (sixteenth - 1)
        return self.sample_at_sixteenth(index)

    def nearest_sixteenth(self, sample: int) -> int:
        """0-based index of the grid sixteenth closest to `sample`."""
        return max(0, round((sample - self.offset) / self.samples_per_sixteenth))

    def distance_to_sixteenth_ms(self, sample: int) -> float:
        """Signed ms from the nearest grid sixteenth to `sample` (positive = late)."""
        grid = self.sample_at_sixteenth(self.nearest_sixteenth(sample))
        return (sample - grid) * 1000.0 / self.sample_rate

    def label(self, sample: int) -> str:
        """`bar.beat.sixteenth` of the grid sixteenth nearest to `sample`."""
        return label_for_sixteenth(self.nearest_sixteenth(sample))

    def sixteenths(self, samples: int) -> float:
        """Length of `samples` in sixteenths."""
        return samples / self.samples_per_sixteenth

    def parse_position(self, text: str) -> int:
        """Sample offset for a position written as samples, seconds or beats.

        `19388` is a sample count, `0.44s` is seconds, `2.3` or `2.3.1` is
        bar 2 beat 3 sixteenth 1. Raises ValueError for anything else.
        """
        text = text.strip()
        if re.fullmatch(r"\d+", text):
            return int(text)
        seconds = re.fullmatch(r"(\d+(?:\.\d*)?|\.\d+)s", text)
        if seconds:
            return round(float(seconds.group(1)) * self.sample_rate)
        beat = _BEAT_POSITION.match(text)
        if beat:
            sixteenth = beat.group("sixteenth")
            return self.sample_at(
                int(beat.group("bar")),
                int(beat.group("beat")),
                1 if sixteenth is None else int(sixteenth),
            )
        raise ValueError(
            f"cannot read position {text!r}: use samples (19388), seconds (0.44s) "
            "or beats (bar.beat or bar.beat.sixteenth, 1-based)"
        )


def label_for_sixteenth(index: int) -> str:
    """`bar.beat.sixteenth` (1-based) for a 0-based sixteenth index."""
    if index < 0:
        raise ValueError(f"sixteenth index must be >= 0, got {index}")
    bar, rest = divmod(index, SIXTEENTHS_PER_BAR)
    beat, sixteenth = divmod(rest, SIXTEENTHS_PER_BEAT)
    return f"{bar + 1}.{beat + 1}.{sixteenth + 1}"
