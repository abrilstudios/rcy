"""
Enumerations for RCY application using Python 3.11+ StrEnum.

This module defines string-based enumerations for various constants used
throughout the application, providing type safety and IDE autocomplete support.
"""

from enum import StrEnum


class PlaybackMode(StrEnum):
    """Playback mode options for audio segments.

    Attributes:
        ONE_SHOT: Play once and stop
        LOOP: Loop continuously in forward direction
        LOOP_REVERSE: Loop with alternating forward/reverse playback
    """
    ONE_SHOT = "one-shot"
    LOOP = "loop"
    LOOP_REVERSE = "loop-reverse"


class SplitMethod(StrEnum):
    """Methods for splitting audio into segments.

    Attributes:
        MEASURES: Split based on musical measures and tempo
        TRANSIENTS: Split based on transient detection (onset detection)
    """
    MEASURES = "measures"
    TRANSIENTS = "transients"


class ExportFormat(StrEnum):
    """Audio export format options.

    Attributes:
        WAV: Uncompressed WAV audio format
        FLAC: Lossless FLAC compression
        MP3: Lossy MP3 compression
    """
    WAV = "wav"
    FLAC = "flac"
    MP3 = "mp3"


class FadeCurve(StrEnum):
    """Fade curve types for tail fade effects.

    Attributes:
        LINEAR: Linear fade curve
        EXPONENTIAL: Exponential fade curve for more natural sound
        LOGARITHMIC: Logarithmic fade curve
    """
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    LOGARITHMIC = "logarithmic"
