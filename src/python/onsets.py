"""Onset (transient) detection as a pure function of an audio array.

`detect_onsets` wraps librosa's onset strength envelope and peak picker
and returns sample offsets. The TUI's transient split calls it with the
`transientDetection` settings from config.json (frame-level precision,
hop 512). Headless tools call `detect_onsets_precise`, which runs the same
detector with a 64-sample hop and backtracking so every onset lands at the
start of its attack, close enough to cut 3 ms in front of it.
"""

from __future__ import annotations

import librosa
import numpy as np

from custom_types import AudioArray

# Sample-accurate settings for cutting: 64-sample hop (1.5 ms at 44.1 kHz),
# backtracked to the attack, peaks at least 8 hops (11.6 ms) apart.
PRECISE_HOP_LENGTH = 64
PRECISE_N_FFT = 1024
PRECISE_DELTA = 0.06
PRECISE_WAIT = 8
PRECISE_PRE_MAX = 6
PRECISE_POST_MAX = 6


def detect_onsets(
    signal: AudioArray,
    sample_rate: int,
    *,
    delta: float,
    wait: int,
    pre_max: int,
    post_max: int,
    hop_length: int = 512,
    n_fft: int = 2048,
    backtrack: bool = False,
) -> list[int]:
    """Onset positions in samples, ascending, for a mono signal.

    `delta`, `wait`, `pre_max` and `post_max` are librosa peak-picking
    parameters in frames of `hop_length` samples. With `backtrack` each
    peak is moved back to the preceding minimum of the strength envelope,
    the start of the attack.
    """
    if len(signal) == 0:
        return []
    envelope = librosa.onset.onset_strength(
        y=np.asarray(signal, dtype=np.float32), sr=sample_rate, hop_length=hop_length, n_fft=n_fft
    )
    frames = librosa.onset.onset_detect(
        onset_envelope=envelope,
        sr=sample_rate,
        hop_length=hop_length,
        delta=delta,
        wait=wait,
        pre_max=pre_max,
        post_max=post_max,
        backtrack=backtrack,
    )
    samples = librosa.frames_to_samples(frames, hop_length=hop_length)
    return [int(s) for s in samples if 0 <= int(s) < len(signal)]


def detect_onsets_precise(signal: AudioArray, sample_rate: int) -> list[int]:
    """`detect_onsets` with the sample-accurate settings used for cutting."""
    return detect_onsets(
        signal,
        sample_rate,
        delta=PRECISE_DELTA,
        wait=PRECISE_WAIT,
        pre_max=PRECISE_PRE_MAX,
        post_max=PRECISE_POST_MAX,
        hop_length=PRECISE_HOP_LENGTH,
        n_fft=PRECISE_N_FFT,
        backtrack=True,
    )


def nearest_onset(sample: int, onsets: list[int]) -> int | None:
    """The onset closest to `sample`, or None when there are no onsets."""
    if not onsets:
        return None
    return min(onsets, key=lambda o: (abs(o - sample), o))
