# export_utils.py

import os
import numpy as np
import soundfile as sf
from midiutil import MIDIFile
from config_manager import config
from audio_processor import process_segment_for_output

class MIDIFileWithMetadata(MIDIFile):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tempo = None
        self.time_signature = None
        self.total_time = 0
        self.notes = []

    def addTempo(self, track, time, tempo):
        self.tempo = tempo
        super().addTempo(track, time, tempo)

    def addTimeSignature(self, track, time, numerator, denominator, clocks_per_tick, notes_per_quarter=8):
        # Store as (numerator, denominator_value) for debugging
        # Where denominator_value is 2^denominator (the actual denominator in the time signature)
        self.time_signature = (numerator, 2**denominator)
        super().addTimeSignature(track, time, numerator, denominator, clocks_per_tick, notes_per_quarter)

    def addNote(self, track, channel, pitch, time, duration, volume, annotation=None):
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
    def export_segments(model, tempo, num_measures, directory, start_marker_pos=None, end_marker_pos=None):
        segments = model.get_segments()
        # Get left and right channel data
        data_left = model.data_left
        data_right = model.data_right
        is_stereo = model.is_stereo
        sample_rate = model.sample_rate
        
        # Debug segments info
        print("\n==== EXPORT SEGMENTS DEBUG ====")
        print(f"Debug: Segments from model: {segments}")
        print(f"Debug: Number of segments from model: {len(segments)}")
        print(f"Debug: Segment boundary points (in samples): {segments}")
        print(f"Debug: Segment boundary points (in seconds): {[s/sample_rate for s in segments]}")
        
        # Use left channel for calculations (both channels have same length)
        total_duration = len(data_left) / sample_rate
        tempo = model.get_tempo(num_measures)

        # Get the playback tempo settings from the model
        playback_tempo_enabled = model.playback_tempo_enabled
        source_bpm = model.source_bpm
        target_bpm = model.target_bpm
        
        # Get tail fade settings from config
        tail_fade_config = config.get_setting("audio", "tailFade", {})
        tail_fade_enabled = tail_fade_config.get("enabled", False)
        fade_duration_ms = tail_fade_config.get("durationMs", 10)
        fade_curve = tail_fade_config.get("curve", "exponential")

        print(f"Debug: Total duration: {total_duration} seconds")
        print(f"Debug: Tempo: {tempo} BPM")
        print(f"Debug: Number of segments: {len(segments)}")
        print(f"Debug: Is stereo: {is_stereo}")
        print(f"Debug: Playback tempo enabled: {playback_tempo_enabled}")
        if playback_tempo_enabled:
            print(f"Debug: Source BPM: {source_bpm}, Target BPM: {target_bpm}")
        print(f"Debug: Tail fade enabled: {tail_fade_enabled}")

        sfz_content = []
        midi = MIDIFileWithMetadata(1)  # One track
        midi.addTempo(0, 0, tempo)
        # In the MIDI specification, the time signature denominator is encoded as a power of 2.
        # The parameter represents the exponent rather than the actual denominator value.
        # For 4/4 time signature: numerator=4, denominator=2 (where 2^2 = 4)
        midi.addTimeSignature(0, 0, 4, 2, 24, 8)  # 4/4 time signature (denominator=2 for quarter notes)

        # Check if we have markers set but no segments
        if (not segments) and start_marker_pos is not None and end_marker_pos is not None:
            print(f"No segments defined but markers are set. Using marker positions for export.")
            # Convert marker time positions to sample positions
            start_sample = int(start_marker_pos * sample_rate)
            end_sample = int(end_marker_pos * sample_rate)
            # Create a segment list with just these markers
            segments = [start_sample, end_sample]
            print(f"Created segments from markers: {segments[0]} to {segments[1]} samples")
            
        # If still no segments, use the entire file
        if not segments:
            print(f"Debug: No segments or markers. Exporting the entire file.")
            segments = [0, len(data_left)]
        else:
            # Always ensure we have the file start and end in the segments
            print(f"Debug: Original segments from model: {segments}")
            
            # Add file start (0) if not present
            if 0 not in segments:
                print(f"Debug: Adding file start (0) to segments array")
                segments.insert(0, 0)
            
            # Add file end if not present
            if len(data_left) not in segments:
                print(f"Debug: Adding file end ({len(data_left)}) to segments array")
                segments.append(len(data_left))
                
            # Sort to ensure proper order
            segments.sort()
            print(f"Debug: Final segments with boundaries: {segments}")

        # Calculate beats per second
        beats_per_second = tempo / 60
        
        # Pre-count valid segments and generate debug info
        valid_segments = []
        for i, (start, end) in enumerate(zip(segments[:-1], segments[1:])):
            if start == end:
                print(f"Debug: Will skip zero-length segment at position {start}")
                continue
            valid_segments.append((i, start, end))
        
        print(f"Debug: Found {len(valid_segments)} valid segments out of {len(segments)-1} total segments")
        
        # Detailed segment-to-MIDI mapping report
        print("\n==== SEGMENT TO MIDI MAPPING ====")
        print(f"Debug: Tempo: {tempo} BPM, beats per second: {beats_per_second}")
        for idx, (i, start, end) in enumerate(valid_segments):
            start_time = start / sample_rate
            duration = (end - start) / sample_rate
            start_beat = start_time * beats_per_second
            duration_beats = duration * beats_per_second
            
            print(f"Debug: Segment {idx+1} (original {i+1}):")
            print(f"  - Samples: {start} to {end}")
            print(f"  - Time: {start_time:.3f}s to {start_time+duration:.3f}s (duration: {duration:.3f}s)")
            print(f"  - MIDI: start beat {start_beat:.3f}, duration {duration_beats:.3f} beats, MIDI note {60+idx}")
        
        print("\n==== GENERATING SEGMENTS ====")
        # Counter for actual exported segments (used for MIDI notes)
        segment_count = 0
        
        for i, (start, end) in enumerate(zip(segments[:-1], segments[1:])):
            # Skip segments of zero length
            if start == end:
                print(f"Debug: Skipping zero-length segment at position {start}")
                continue
                
            # Increment segment counter for valid segments
            segment_count += 1
            print(f"Debug: Processing segment {segment_count} (original index {i+1}): {start} to {end}")
            
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
            
            segment_filename = f"segment_{segment_count}.wav"
            segment_path = os.path.join(directory, segment_filename)
            
            print(f"Debug: Exporting segment with sample rate: {export_sample_rate} Hz")
            sf.write(segment_path, segment_data, export_sample_rate)

            # Add to SFZ content
            sfz_content.append(f"""
<region>
sample={segment_filename}
pitch_keycenter={60 + segment_count - 1}
lokey={60 + segment_count - 1}
hikey={60 + segment_count - 1}
""")

            # Calculate beat positions based on source tempo
            # This ensures MIDI sequence aligns with exported audio
            start_beat = start / sample_rate * beats_per_second
            
            # If tempo adjustment is applied, the duration changes too
            if playback_tempo_enabled and source_bpm > 0 and target_bpm > 0:
                duration_seconds = (end - start) / sample_rate
                # Scale duration based on tempo change
                adjusted_duration = duration_seconds * (source_bpm / target_bpm)
                duration_beats = adjusted_duration * beats_per_second
            else:
                duration_beats = (end - start) / sample_rate * beats_per_second
            
            # Use segment_count instead of i to align with WAV files
            midi_note = 60 + segment_count - 1
            midi.addNote(0, 0, midi_note, start_beat, duration_beats, 100)

            print(f"Debug: Segment {segment_count} (original index {i+1}): start={start/sample_rate:.2f}s, duration={(end-start)/sample_rate:.2f}s, note={midi_note}, start_beat={start_beat:.2f}, duration_beats={duration_beats:.2f}")

        # MIDI file debug information
        print("\n==== MIDI EXPORT SUMMARY ====")
        print(f"Tempo: {midi.tempo} BPM")
        print(f"Time Signature: {midi.time_signature[0]}/{midi.time_signature[1]}")
        print(f"Total MIDI duration (beats): {midi.total_time:.2f}")
        print(f"Total MIDI duration (seconds): {midi.total_time / beats_per_second:.2f}")
        
        # Segment counts
        total_segments = len(segments) - 1
        non_zero_segments = sum(1 for start, end in zip(segments[:-1], segments[1:]) if start != end)
        zero_segments = total_segments - non_zero_segments
        
        print(f"\n==== SEGMENT STATISTICS ====")
        print(f"Total boundary points: {len(segments)}")
        print(f"Total segments: {total_segments} (distinct slice pairs)")
        print(f"Non-zero segments: {non_zero_segments}")
        print(f"Zero-length segments: {zero_segments}")
        print(f"Exported WAV files: {segment_count}")
        print(f"MIDI notes count: {len(midi.notes)}")
        
        # Sanity checks
        if segment_count != len(midi.notes):
            print("\n⚠️ WARNING: WAV segment count and MIDI note count don't match!")
            print(f"  - WAV segments: {segment_count}")
            print(f"  - MIDI notes: {len(midi.notes)}")
        else:
            print("\n✅ VALIDATION: WAV segment count and MIDI note count match correctly.")
        
        print(f"\n==== MIDI NOTES DETAIL ====")
        for i, note in enumerate(midi.notes):
            print(f"  Note {i+1}: pitch={note['pitch']} start={note['time']:.2f} duration={note['duration']:.2f}")
        
        print(f"\n==== SEGMENT BOUNDARIES ====")
        print(f"Segments array (samples): {segments}")
        print(f"Segments durations (seconds): {[(end-start)/sample_rate for start, end in zip(segments[:-1], segments[1:])]}")

        # Write SFZ file
        sfz_path = os.path.join(directory, "instrument.sfz")
        with open(sfz_path, 'w') as sfz_file:
            sfz_file.write("\n".join(sfz_content))

        # Write MIDI file
        midi_path = os.path.join(directory, "sequence.mid")
        with open(midi_path, "wb") as midi_file:
            midi.writeFile(midi_file)

        print(f"Exported {len(segments) - 1} segments, SFZ file, and MIDI file to {directory}")
