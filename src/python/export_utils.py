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

    def addTempo(self, track, time, tempo):
        self.tempo = tempo
        super().addTempo(track, time, tempo)

    def addTimeSignature(self, track, time, numerator, denominator, clocks_per_tick, notes_per_quarter=8):
        self.time_signature = (numerator, denominator)
        super().addTimeSignature(track, time, numerator, denominator, clocks_per_tick, notes_per_quarter)

    def addNote(self, track, channel, pitch, time, duration, volume, annotation=None):
        self.total_time = max(self.total_time, time + duration)
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
        midi.addTimeSignature(0, 0, 4, 4, 24, 8)  # Assuming 4/4 time signature

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
            print(f"No segments or markers. Exporting the entire file.")
            segments = [0, len(data_left)]
            
        # Ensure the first segment starts at 0 and the last ends at the audio length
        elif segments[0] != 0 and (start_marker_pos is None or start_marker_pos > 0):
            segments.insert(0, 0)
            
        if segments[-1] != len(data_left) and (end_marker_pos is None or end_marker_pos < total_duration):
            segments.append(len(data_left))

        # Calculate beats per second
        beats_per_second = tempo / 60

        for i, (start, end) in enumerate(zip(segments[:-1], segments[1:])):
            # Skip segments of zero length
            if start == end:
                print(f"Debug: Skipping zero-length segment at position {start}")
                continue
                
            print(f"Debug: Processing segment {i+1}: {start} to {end}")
            
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
            
            segment_filename = f"segment_{i+1}.wav"
            segment_path = os.path.join(directory, segment_filename)
            
            print(f"Debug: Exporting segment with sample rate: {export_sample_rate} Hz")
            sf.write(segment_path, segment_data, export_sample_rate)

            # Add to SFZ content
            sfz_content.append(f"""
<region>
sample={segment_filename}
pitch_keycenter={60 + i}
lokey={60 + i}
hikey={60 + i}
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
            
            midi.addNote(0, 0, 60 + i, start_beat, duration_beats, 100)

            print(f"Debug: Segment {i+1}: start={start/sample_rate:.2f}s, duration={(end-start)/sample_rate:.2f}s, start_beat={start_beat:.2f}, duration_beats={duration_beats:.2f}")

        # MIDI file debug information
        print("\nMIDI File Debug Information:")
        print(f"Tempo: {midi.tempo} BPM")
        print(f"Time Signature: {midi.time_signature[0]}/{midi.time_signature[1]}")
        print(f"Total MIDI duration (beats): {midi.total_time:.2f}")
        print(f"Total MIDI duration (seconds): {midi.total_time / beats_per_second:.2f}")
        print(f"Total number of segments: {len(segments) - 1}")

        # Write SFZ file
        sfz_path = os.path.join(directory, "instrument.sfz")
        with open(sfz_path, 'w') as sfz_file:
            sfz_file.write("\n".join(sfz_content))

        # Write MIDI file
        midi_path = os.path.join(directory, "sequence.mid")
        with open(midi_path, "wb") as midi_file:
            midi.writeFile(midi_file)

        print(f"Exported {len(segments) - 1} segments, SFZ file, and MIDI file to {directory}")
