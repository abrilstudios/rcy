"""
Type definitions for RCY application.

This module defines common types, aliases, and TypedDict structures
used throughout the RCY codebase.
"""

from typing import Any, Callable, Protocol, TypedDict

import numpy as np
import numpy.typing as npt

# NumPy array type aliases
AudioArray = npt.NDArray[np.float64]  # Standard audio data array
TimeArray = npt.NDArray[np.float64]   # Time array for waveform display
SampleArray = npt.NDArray[np.int32]   # Sample position array


# Configuration TypedDict definitions
class PresetInfo(TypedDict, total=False):
    """Information about an audio preset."""
    name: str
    filepath: str
    measures: int
    description: str


class PlaybackTempoConfig(TypedDict, total=False):
    """Playback tempo configuration."""
    enabled: bool
    targetBpm: int


class TailFadeConfig(TypedDict, total=False):
    """Tail fade configuration."""
    enabled: bool
    durationMs: int
    curve: str


class TransientDetectionConfig(TypedDict, total=False):
    """Transient detection configuration."""
    threshold: float
    waitTime: int
    preMax: int
    postMax: int
    deltaFactor: float


class AudioConfig(TypedDict, total=False):
    """Audio configuration section."""
    playbackTempo: PlaybackTempoConfig
    tailFade: TailFadeConfig
    transientDetection: TransientDetectionConfig


class ExportStats(TypedDict, total=False):
    """Statistics returned from export operation."""
    segment_count: int
    sfz_path: str
    midi_path: str
    tempo: float
    time_signature: tuple[int, int]
    directory: str
    duration: float
    wav_files: int
    start_time: float
    end_time: float
    playback_tempo_enabled: bool
    source_bpm: float
    target_bpm: int


class SegmentInfo(TypedDict):
    """Information about a processed segment."""
    index: int
    start_sample: int
    end_sample: int
    start_time: float
    duration_seconds: float
    start_beat: float
    duration_beats: float
    segment_number: int
    midi_note: int


class WavFileSegment(TypedDict):
    """Information about an exported WAV file segment."""
    filename: str
    path: str
    midi_note: int
    duration: float


# Type aliases for common function signatures
SegmentBoundary = tuple[float, float]  # (start_time, end_time)
SegmentPair = tuple[int, int]          # (start_sample, end_sample)
ColorHex = str                         # Color in hex format like "#RRGGBB"

# Callback type aliases
PlaybackEndedCallback = Callable[[], None]
SegmentChangedCallback = Callable[[str], None]


# Protocol definitions
class SegmentObserverProtocol(Protocol):
    """Protocol for objects that observe segment changes."""

    def on_segments_changed(self, operation: str, **kwargs: Any) -> None:
        """Called when segments are modified."""
        ...


class AudioEngineProtocol(Protocol):
    """Protocol for audio playback engines."""

    def set_source_audio(
        self,
        data_left: AudioArray,
        data_right: AudioArray,
        sample_rate: int,
        is_stereo: bool
    ) -> None:
        """Set the source audio data."""
        ...

    def play_segment(
        self,
        start_time: float,
        end_time: float,
        reverse: bool = False
    ) -> bool:
        """Play a segment of audio."""
        ...

    def stop_playback(self) -> None:
        """Stop any currently playing audio."""
        ...

    def start_stream(self) -> None:
        """Start the audio stream."""
        ...

    def set_playback_tempo(
        self,
        enabled: bool,
        source_bpm: float,
        target_bpm: int
    ) -> None:
        """Set playback tempo parameters."""
        ...

    def set_playback_ended_callback(self, callback: PlaybackEndedCallback) -> None:
        """Set callback for when playback ends."""
        ...

    def on_segments_updated(self, operation: str, **kwargs: Any) -> None:
        """Handle segment update notifications."""
        ...
