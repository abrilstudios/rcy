# export_utils.py

import logging
import os
from typing import Any

import soundfile as sf
from midiutil import MIDIFile

from audio_utils import process_segment_for_output
from config_manager import config
from custom_types import ExportStats
from kit_manifest import (
    KitManifest,
    SourceAudio,
    export_stem,
    manifest_path_for,
    slices_from_boundaries,
)
from sfz_writers import write_sfz

logger = logging.getLogger(__name__)


class MIDIFileWithMetadata(MIDIFile):
    tempo: float | None
    time_signature: tuple[int, int] | None
    total_time: float
    notes: list[dict[str, Any]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.tempo = None
        self.time_signature = None
        self.total_time = 0
        self.notes = []

    def addTempo(self, track: int, time: float, tempo: float) -> None:  # noqa: N802
        self.tempo = tempo
        super().addTempo(track, time, tempo)

    def addTimeSignature(  # noqa: N802
        self,
        track: int,
        time: float,
        numerator: int,
        denominator: int,
        clocks_per_tick: int,
        notes_per_quarter: int = 8,
    ) -> None:
        # The MIDI spec encodes the denominator as a power of two; keep the real value.
        self.time_signature = (numerator, 2**denominator)
        super().addTimeSignature(
            track, time, numerator, denominator, clocks_per_tick, notes_per_quarter
        )

    def addNote(  # noqa: N802
        self,
        track: int,
        channel: int,
        pitch: int,
        time: float,
        duration: float,
        volume: int,
        annotation: str | None = None,
    ) -> None:
        self.total_time = max(self.total_time, time + duration)
        self.notes.append({
            "track": track,
            "channel": channel,
            "pitch": pitch,
            "time": time,
            "duration": duration,
            "volume": volume,
        })
        super().addNote(track, channel, pitch, time, duration, volume, annotation)


def export_kit(
    manifest: KitManifest,
    audio: SourceAudio,
    directory: str,
    sfz_dialect: str = "files",
    target_bpm: float | None = None,
    render_slices: bool = True,
) -> ExportStats:
    """Export `manifest` from `audio` into `directory`.

    Writes `<index>.wav` per slice when `render_slices`, `<stem>.sfz` in
    `sfz_dialect`, `<stem>.mid` with one note per slice (each slice's role
    as a text event at its note), and `<stem>.rcy.json`. `manifest.source`
    is rewritten relative to `directory` before saving. When `target_bpm`
    is given, slices are time-stretched from `manifest.bpm` to it and the
    MIDI file is written at that tempo.
    """
    manifest.validate()
    stem = export_stem(directory)
    manifest = manifest.rebased(audio.path, directory)

    tail_fade_config = config.get_setting("audio", "tailFade", {})
    tail_fade_enabled = tail_fade_config.get("enabled", False)
    fade_duration_ms = tail_fade_config.get("durationMs", 10)
    fade_curve = tail_fade_config.get("curve", "exponential")

    tempo_adjust = target_bpm is not None and target_bpm > 0
    midi_tempo = target_bpm if tempo_adjust and target_bpm is not None else manifest.bpm
    beats_per_second = midi_tempo / 60

    midi = MIDIFileWithMetadata(1)
    midi.addTempo(0, 0, midi_tempo)
    midi.addTimeSignature(0, 0, 4, 2, 24, 8)  # 4/4; denominator 2 means 2**2

    next_beat = 0.0
    for s in manifest.slices:
        if render_slices:
            segment_data, export_sample_rate = process_segment_for_output(
                audio.data_left,
                audio.data_right,
                s.start,
                s.end,
                manifest.sample_rate,
                audio.is_stereo,
                False,
                tempo_adjust,
                manifest.bpm,
                target_bpm,
                tail_fade_enabled,
                fade_duration_ms,
                fade_curve,
                for_export=True,
                resample_on_export=True,
            )
            sf.write(os.path.join(directory, s.file), segment_data, export_sample_rate)

        duration_seconds = (s.end - s.start) / manifest.sample_rate
        if tempo_adjust and target_bpm is not None:
            duration_seconds *= manifest.bpm / target_bpm
        duration_beats = duration_seconds * beats_per_second
        midi.addNote(0, 0, s.key, next_beat, duration_beats, 100)
        if s.role:
            midi.addText(0, next_beat, s.role)
        next_beat += duration_beats
        logger.debug("slice %s: %s..%s -> %s key %s", s.index, s.start, s.end, s.file, s.key)

    sfz_path = os.path.join(directory, f"{stem}.sfz")
    with open(sfz_path, "w") as sfz_file:
        sfz_file.write(write_sfz(sfz_dialect, manifest.source, manifest.slices))

    midi_path = os.path.join(directory, f"{stem}.mid")
    with open(midi_path, "wb") as midi_file:
        midi.writeFile(midi_file)

    manifest_path = manifest_path_for(directory)
    manifest.save(manifest_path)

    logger.debug("Exported %s slices, SFZ, MIDI, manifest to %s", len(manifest.slices), directory)
    total_duration = audio.total_time
    return {
        "segment_count": len(manifest.slices),
        "sfz_path": sfz_path,
        "midi_path": midi_path,
        "manifest_path": manifest_path,
        "tempo": midi_tempo,
        "time_signature": midi.time_signature,
        "directory": directory,
        "duration": total_duration,
        "wav_files": len(manifest.slices) if render_slices else 0,
        "start_time": 0,
        "end_time": total_duration,
        "playback_tempo_enabled": tempo_adjust,
        "source_bpm": manifest.bpm,
        "target_bpm": target_bpm,
    }


def manifest_from_model(
    model: Any, num_measures: int, segments: list[tuple[float, float]]
) -> KitManifest:
    """Manifest for a loaded WavAudioProcessor and its (start, end) second pairs."""
    sample_rate = model.sample_rate
    cut_points = sorted({int(t * sample_rate) for pair in segments for t in pair})
    return KitManifest(
        source=os.path.abspath(model.filename),
        sample_rate=sample_rate,
        channels=2 if model.is_stereo else 1,
        bpm=float(model.source_bpm),
        measures=num_measures,
        region=(cut_points[0], cut_points[-1]),
        boundaries=cut_points,
        slices=slices_from_boundaries(cut_points),
    )


class ExportUtils:
    @staticmethod
    def export_segments(
        model: Any,  # WavAudioProcessor; Any avoids a circular import
        tempo: float,
        num_measures: int,
        directory: str,
        start_marker_pos: float | None = None,
        end_marker_pos: float | None = None,
        sfz_dialect: str = "files",
    ) -> ExportStats:
        """Export a model's segments as WAV slices, SFZ, MIDI and a kit manifest.

        `tempo` is unused; the source tempo comes from `model.source_bpm` and
        the MIDI tempo from `model.target_bpm` when playback tempo is enabled.
        """
        all_segments = model.segment_manager.get_all_segments()
        total_duration = len(model.data_left) / model.sample_rate
        if not all_segments and start_marker_pos is not None and end_marker_pos is not None:
            all_segments = [(start_marker_pos, end_marker_pos)]
        if not all_segments:
            all_segments = [(0.0, total_duration)]

        manifest = manifest_from_model(model, num_measures, all_segments)
        audio = SourceAudio(
            path=manifest.source,
            sample_rate=model.sample_rate,
            channels=manifest.channels,
            data_left=model.data_left,
            data_right=model.data_right,
        )
        target_bpm = None
        if model.playback_tempo_enabled and model.target_bpm > 0:
            target_bpm = model.target_bpm
        return export_kit(
            manifest, audio, directory, sfz_dialect=sfz_dialect, target_bpm=target_bpm
        )
