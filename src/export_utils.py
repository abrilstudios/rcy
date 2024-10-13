# export_utils.py

import os
import soundfile as sf
from midiutil import MIDIFile

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
    def export_segments(model, tempo, num_bars, directory):
        segments = model.get_segments()
        audio_data = model.data
        sample_rate = model.sample_rate
        total_duration = len(audio_data) / sample_rate
        tempo = model.get_tempo(num_bars)

        print(f"Debug: Total duration: {total_duration} seconds")
        print(f"Debug: Tempo: {tempo} BPM")
        print(f"Debug: Number of segments: {len(segments)}")

        sfz_content = []
        midi = MIDIFileWithMetadata(1)  # One track
        midi.addTempo(0, 0, tempo)
        midi.addTimeSignature(0, 0, 4, 4, 24, 8)  # Assuming 4/4 time signature

        # Ensure the first segment starts at 0 and the last ends at the audio length
        if segments[0] != 0:
            segments.insert(0, 0)
        if segments[-1] != len(audio_data):
            segments.append(len(audio_data))

        # Calculate beats per second
        beats_per_second = tempo / 60

        for i, (start, end) in enumerate(zip(segments[:-1], segments[1:])):
            # Export audio segment
            segment_data = audio_data[start:end]
            segment_filename = f"segment_{i+1}.wav"
            segment_path = os.path.join(directory, segment_filename)
            sf.write(segment_path, segment_data, sample_rate)

            # Add to SFZ content
            sfz_content.append(f"""
<region>
sample={segment_filename}
pitch_keycenter={60 + i}
lokey={60 + i}
hikey={60 + i}
""")

            # Add to MIDI file
            start_beat = start / sample_rate * beats_per_second
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
