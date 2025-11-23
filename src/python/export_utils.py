# export_utils.py

import os
import numpy as np
import soundfile as sf
from midiutil import MIDIFile
from typing import Any

from config_manager import config
from audio_processor import process_segment_for_output
from custom_types import ExportStats, SegmentInfo, WavFileSegment, AudioArray

import logging

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

    def addTempo(self, track: int, time: float, tempo: float) -> None:
        self.tempo = tempo
        super().addTempo(track, time, tempo)

    def addTimeSignature(
        self,
        track: int,
        time: float,
        numerator: int,
        denominator: int,
        clocks_per_tick: int,
        notes_per_quarter: int = 8
    ) -> None:
        # Store as (numerator, denominator_value) for debugging
        # Where denominator_value is 2^denominator (the actual denominator in the time signature)
        self.time_signature = (numerator, 2**denominator)
        super().addTimeSignature(track, time, numerator, denominator, clocks_per_tick, notes_per_quarter)

    def addNote(
        self,
        track: int,
        channel: int,
        pitch: int,
        time: float,
        duration: float,
        volume: int,
        annotation: str | None = None
    ) -> None:
        self.total_time = max(self.total_time, time + duration)
        # Track each note for debugging
        self.notes.append({
            'track': track,
            'channel': channel,
            'pitch': pitch,
            'time': time,
            'duration': duration,
            'volume': volume
        })
        super().addNote(track, channel, pitch, time, duration, volume, annotation)

class ExportUtils:
    @staticmethod
    def export_segments(
        model: Any,  # WavAudioProcessor type - using Any to avoid circular import
        tempo: float,
        num_measures: int,
        directory: str,
        start_marker_pos: float | None = None,
        end_marker_pos: float | None = None
    ) -> ExportStats:
        """Export segments to WAV files with SFZ instrument and MIDI sequence

        Args:
            model: Audio model with segment data (WavAudioProcessor)
            tempo: UNUSED - kept for backward compatibility
            num_measures: UNUSED - kept for backward compatibility
            directory: Directory to export to
            start_marker_pos: Optional start marker position (seconds)
            end_marker_pos: Optional end marker position (seconds)

        Returns:
            Export statistics including segment count, file paths, tempo, etc.

        Note:
            Tempo is now read directly from model.source_bpm and model.target_bpm
            rather than being calculated from num_measures.
        """
        # Get segments from SegmentManager (guaranteed to cover full file)
        all_segments = model.segment_manager.get_all_segments()
        # Get left and right channel data
        data_left = model.data_left
        data_right = model.data_right
        is_stereo = model.is_stereo
        sample_rate = model.sample_rate
        
        # Get the directory name to use for file naming
        dir_name = os.path.basename(os.path.normpath(directory))
        # Default to "instrument"/"sequence" if directory name is empty or just a path separator
        if not dir_name or dir_name == os.path.sep:
            dir_name = "instrument"
        
        # Debug segments info
        logger.debug("\n==== EXPORT SEGMENTS DEBUG ====")
        logger.debug("Debug: Segments from SegmentManager: %s", len(all_segments))
        logger.debug("Debug: Segment time ranges: %s", [(s[0], s[1]) for s in all_segments])
        
        # Use left channel for calculations (both channels have same length)
        total_duration = len(data_left) / sample_rate

        # Get the playback tempo settings from the model
        playback_tempo_enabled = model.playback_tempo_enabled
        source_bpm = model.source_bpm
        target_bpm = model.target_bpm
        
        # Get tail fade settings from config
        tail_fade_config = config.get_setting("audio", "tailFade", {})
        tail_fade_enabled = tail_fade_config.get("enabled", False)
        fade_duration_ms = tail_fade_config.get("durationMs", 10)
        fade_curve = tail_fade_config.get("curve", "exponential")

        logger.debug("Debug: Number of segments: %s", len(all_segments))
        logger.debug("Debug: Source BPM: %s", source_bpm)
        logger.debug("Debug: Is stereo: %s", is_stereo)
        if playback_tempo_enabled:
            logger.debug("Debug: Playback tempo enabled - Target BPM: %s", target_bpm)

        sfz_content = []
        midi = MIDIFileWithMetadata(1)  # One track

        # Use the target BPM for MIDI if playback tempo adjustment is enabled
        midi_tempo = target_bpm if playback_tempo_enabled and target_bpm > 0 else source_bpm
        logger.debug("Debug: Using tempo for MIDI export: %s BPM", midi_tempo)

        midi.addTempo(0, 0, midi_tempo)
        # In the MIDI specification, the time signature denominator is encoded as a power of 2.
        # The parameter represents the exponent rather than the actual denominator value.
        # For 4/4 time signature: numerator=4, denominator=2 (where 2^2 = 4)
        midi.addTimeSignature(0, 0, 4, 2, 24, 8)  # 4/4 time signature (denominator=2 for quarter notes)

        # Handle special cases for segment sources
        if not all_segments and start_marker_pos is not None and end_marker_pos is not None:
            # Create segments from markers
            all_segments = [(start_marker_pos, end_marker_pos)]
            logger.debug("Created segments from markers: %s", all_segments)

        # If still no segments, use the entire file
        if not all_segments:
            all_segments = [(0.0, total_duration)]
            logger.debug("No segments defined, using entire file: %s", all_segments)

        logger.debug("Debug: Final segments for export: %s", all_segments)

        # Calculate beats per second based on the MIDI tempo we defined earlier
        beats_per_second = midi_tempo / 60
        logger.debug("Debug: Beats per second: %s", beats_per_second)
        
        # Helper function for MIDI timing strategies
        def _preprocess_segment_pairs(
            segment_pairs: list[tuple[float, float]],
            sample_rate: int,
            playback_tempo_enabled: bool,
            source_bpm: float,
            target_bpm: int,
            beats_per_second: float
        ) -> list[SegmentInfo]:
            """Pre-process segment pairs to calculate timing information - NO SKIPPING OF ZERO-LENGTH SEGMENTS"""
            processed_segments: list[SegmentInfo] = []

            # Process each segment pair directly (start_time, end_time)
            for i, (start_time, end_time) in enumerate(segment_pairs):
                duration_seconds = end_time - start_time

                # Calculate MIDI beat positions and durations
                start_beat = start_time * beats_per_second

                # If tempo adjustment is applied, adjust duration
                if playback_tempo_enabled and source_bpm > 0 and target_bpm > 0:
                    # Scale duration based on tempo change
                    adjusted_duration = duration_seconds * (source_bpm / target_bpm)
                    duration_beats = adjusted_duration * beats_per_second
                else:
                    duration_beats = duration_seconds * beats_per_second

                # Convert back to samples for export processing
                start_sample = int(start_time * sample_rate)
                end_sample = int(end_time * sample_rate)

                # Store all information about this segment - INCLUDING ZERO-LENGTH SEGMENTS
                processed_segments.append({
                    'index': i,
                    'start_sample': start_sample,
                    'end_sample': end_sample,
                    'start_time': start_time,
                    'duration_seconds': duration_seconds,
                    'start_beat': start_beat,
                    'duration_beats': duration_beats,
                    'segment_number': i + 1,  # 1-based indexing matches keyboard shortcuts
                    'midi_note': 60 + i  # MIDI note matches segment index
                })

                logger.debug("Debug: Processed segment %s: %ss to %ss", i+1, start_time, end_time)

            return processed_segments

        def _apply_continuous_note_timing(
            midi: MIDIFileWithMetadata,
            segment_info_list: list[SegmentInfo]
        ) -> None:
            """Apply continuous timing strategy with no gaps between notes"""
            logger.debug("\nDebug: Using CONTINUOUS timing strategy (no gaps)")

            # Keep track of the next available beat position
            next_beat_position = 0.0

            for i, segment in enumerate(segment_info_list):
                # Use continuous timing (each note starts right after the previous one)
                start_beat = next_beat_position
                duration_beats = segment['duration_beats']
                midi_note = segment['midi_note']

                # Add note to MIDI file with continuous timing
                midi.addNote(0, 0, midi_note, start_beat, duration_beats, 100)

                # Update next available position
                next_beat_position = start_beat + duration_beats

                # Debug output
                logger.debug("Segment %s: start_beat=%s, duration=%s beats",
                      i, start_beat, duration_beats)

                # Show original vs. continuous timing for comparison
                original_start = segment['start_beat']
                if abs(start_beat - original_start) > 0.001:  # Only show if meaningful difference
                    logger.debug("       (Original timing would be: start_beat=%s)", original_start)
        
        # Pre-process all segments to calculate timing information
        logger.debug("\n==== PREPROCESSING SEGMENTS ====")
        all_segment_info = _preprocess_segment_pairs(all_segments, sample_rate, playback_tempo_enabled,
                                                    source_bpm, target_bpm, beats_per_second)

        logger.debug("Preprocessing complete: %s segments for export (NO zero-length segments skipped)", len(all_segment_info))
        
        # Detailed segment-to-MIDI mapping report
        logger.debug("\n==== SEGMENT TO MIDI MAPPING ====")
        logger.debug("Debug: MIDI Tempo: %s BPM, beats per second: %s", midi_tempo, beats_per_second)

        for segment in all_segment_info:
            logger.debug("Segment %s:", segment['segment_number'])
            logger.debug("  - Samples: %s to %s", segment['start_sample'], segment['end_sample'])
            logger.debug("  - MIDI: start beat %s, duration %s beats, note %s",
                  segment['start_beat'], segment['duration_beats'], segment['midi_note'])
        
        logger.debug("\n==== GENERATING SEGMENTS ====")
        # Counter for actual exported segments
        segment_count = 0
        
        # List to store segment information for WAV files
        wavfile_segments = []
        
        for segment in all_segment_info:
            # Get segment information
            start = segment['start_sample']
            end = segment['end_sample']
            segment_count = segment['segment_number']

            logger.debug("Debug: Processing segment %s (original index %s): %s to %s",
                        segment_count, segment['index'], start, end)
            
            # Process the segment through our pipeline with resampling for export
            segment_data, export_sample_rate = process_segment_for_output(
                data_left,
                data_right,
                start,
                end,
                sample_rate,
                is_stereo,
                False,  # No reverse for export
                playback_tempo_enabled,
                source_bpm,
                target_bpm,
                tail_fade_enabled,
                fade_duration_ms,
                fade_curve,
                for_export=True,  # Indicate this is for export
                resample_on_export=True  # Enable resampling back to standard rate
            )
            
            # The returned export_sample_rate will be the original sample rate
            # if resampling was performed, or the adjusted rate if not

            segment_filename = f"{segment_count:03d}.wav"
            segment_path = os.path.join(directory, segment_filename)

            logger.debug("Debug: Exporting segment with sample rate: %s Hz", export_sample_rate)
            sf.write(segment_path, segment_data, export_sample_rate)

            # Add to SFZ content - reference the WAV file using the segment_filename
            sfz_content.append(f"<region> sample={segment_filename} key={segment['midi_note']}")

            # Store info for debug output
            wavfile_segments.append({
                'filename': segment_filename,
                'path': segment_path,
                'midi_note': segment['midi_note'],
                'duration': segment['duration_seconds']
            })

            logger.debug("Debug: Segment %s exported: %s", segment_count, segment_filename)
        
        # Apply continuous MIDI timing strategy
        _apply_continuous_note_timing(midi, all_segment_info)

        # MIDI file debug information
        logger.debug("\n==== MIDI EXPORT SUMMARY ====")
        logger.debug("Tempo: %s BPM", midi.tempo)
        logger.debug("Total MIDI duration (beats): %s", midi.total_time)
        logger.debug("Total MIDI duration (seconds): %.2f", midi.total_time / beats_per_second)
        
        # Segment counts
        total_segments = len(all_segments)
        non_zero_segments = sum(1 for start_time, end_time in all_segments if start_time != end_time)
        zero_segments = total_segments - non_zero_segments
        
        logger.debug("\n==== SEGMENT STATISTICS ====")
        logger.debug("Total segments: %s (from SegmentManager)", total_segments)
        logger.debug("Zero-length segments: %s", zero_segments)
        logger.warning("MIDI notes count: %s", len(midi.notes))
        
        # Sanity checks
        if segment_count != len(midi.notes):
            logger.warning("\n⚠️ WARNING: WAV segment count and MIDI note count don't match!")
            logger.debug("  - WAV segments: %s", segment_count)
            logger.debug("  - MIDI notes: %s", len(midi.notes))
        else:
            logger.debug("\n✅ VALIDATION: WAV segment count and MIDI note count match correctly.")

        logger.debug("\nMIDI notes (%s total):", len(midi.notes))
        for i, note in enumerate(midi.notes):
            logger.debug("  Note %s: pitch=%s start=%s duration=%s",
                        i+1, note['pitch'], note['time'], note['duration'])

        logger.debug("Segments from SegmentManager: %s", len(all_segments))
        logger.debug("Segment durations: %s", [end_time - start_time for start_time, end_time in all_segments])

        # Write SFZ file with directory name
        sfz_filename = f"{dir_name}.sfz"
        sfz_path = os.path.join(directory, sfz_filename)
        with open(sfz_path, 'w') as sfz_file:
            sfz_file.write("\n".join(sfz_content))

        # Write MIDI file with directory name
        midi_filename = f"{dir_name}.mid"
        midi_path = os.path.join(directory, midi_filename)
        with open(midi_path, "wb") as midi_file:
            midi.writeFile(midi_file)

        logger.debug("Exported %s segments, SFZ file, and MIDI file to %s", segment_count, directory)
        
        # Prepare export statistics to return
        export_stats = {
            'segment_count': segment_count,
            'sfz_path': sfz_path,
            'midi_path': midi_path,
            'tempo': midi.tempo,
            'time_signature': midi.time_signature,
            'directory': directory,
            'duration': total_duration,
            'wav_files': segment_count,
            'start_time': 0,
            'end_time': total_duration,
            'playback_tempo_enabled': playback_tempo_enabled,
            'source_bpm': source_bpm,
            'target_bpm': target_bpm
        }
        
        return export_stats
