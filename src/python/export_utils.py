# export_utils.py

import os
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
        """Export segments to WAV files with SFZ instrument and MIDI sequence
        
        Args:
            model: Audio model with segment data
            tempo: Tempo in BPM
            num_measures: Number of measures
            directory: Directory to export to
            start_marker_pos: Optional start marker position (seconds)
            end_marker_pos: Optional end marker position (seconds)
            
        Returns:
            dict: Export statistics including:
                - segment_count: Number of segments exported
                - sfz_path: Path to the SFZ file
                - midi_path: Path to the MIDI file
                - tempo: Tempo used for the export
                - time_signature: Time signature used
                - directory: Export directory
                - duration: Total duration of the audio
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
        print("\n==== EXPORT SEGMENTS DEBUG ====")
        print(f"Debug: Segments from SegmentManager: {all_segments}")
        print(f"Debug: Number of segments from SegmentManager: {len(all_segments)}")
        print(f"Debug: Segment time ranges: {all_segments}")
        
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
        print(f"Debug: Number of segments: {len(all_segments)}")
        print(f"Debug: Is stereo: {is_stereo}")
        print(f"Debug: Playback tempo enabled: {playback_tempo_enabled}")
        if playback_tempo_enabled:
            print(f"Debug: Source BPM: {source_bpm}, Target BPM: {target_bpm}")
        print(f"Debug: Tail fade enabled: {tail_fade_enabled}")

        sfz_content = []
        midi = MIDIFileWithMetadata(1)  # One track
        
        # Use the target BPM for MIDI if playback tempo adjustment is enabled
        midi_tempo = target_bpm if playback_tempo_enabled and target_bpm > 0 else tempo
        print(f"Debug: Using tempo for MIDI export: {midi_tempo} BPM")
        
        midi.addTempo(0, 0, midi_tempo)
        # In the MIDI specification, the time signature denominator is encoded as a power of 2.
        # The parameter represents the exponent rather than the actual denominator value.
        # For 4/4 time signature: numerator=4, denominator=2 (where 2^2 = 4)
        midi.addTimeSignature(0, 0, 4, 2, 24, 8)  # 4/4 time signature (denominator=2 for quarter notes)

        # Handle special cases for segment sources
        if not all_segments and start_marker_pos is not None and end_marker_pos is not None:
            print(f"No segments defined but markers are set. Using marker positions for export.")
            # Create segments from markers
            all_segments = [(start_marker_pos, end_marker_pos)]
            print(f"Created segments from markers: {all_segments}")
            
        # If still no segments, use the entire file
        if not all_segments:
            print(f"Debug: No segments or markers. Exporting the entire file.")
            all_segments = [(0.0, total_duration)]
            
        print(f"Debug: Final segments for export: {all_segments}")

        # Calculate beats per second based on the MIDI tempo we defined earlier
        beats_per_second = midi_tempo / 60 
        print(f"Debug: Beats per second for MIDI calculation: {beats_per_second:.2f}")
        
        # Helper function for MIDI timing strategies
        def _preprocess_segment_pairs(segment_pairs, sample_rate, playback_tempo_enabled, source_bpm, target_bpm, beats_per_second):
            """Pre-process segment pairs to calculate timing information - NO SKIPPING OF ZERO-LENGTH SEGMENTS"""
            processed_segments = []
            
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
                
                print(f"Debug: Processed segment {i+1}: {start_time:.3f}s to {end_time:.3f}s "
                      f"(duration: {duration_seconds:.3f}s)")
            
            return processed_segments
        
        def _apply_continuous_note_timing(midi, segment_info_list):
            """Apply continuous timing strategy with no gaps between notes"""
            print(f"\nDebug: Using CONTINUOUS timing strategy (no gaps)")
            
            # Keep track of the next available beat position
            next_beat_position = 0.0
            
            for segment in segment_info_list:
                # Use continuous timing (each note starts right after the previous one)
                start_beat = next_beat_position
                duration_beats = segment['duration_beats']
                midi_note = segment['midi_note']
                
                # Add note to MIDI file with continuous timing
                midi.addNote(0, 0, midi_note, start_beat, duration_beats, 100)
                
                # Update next available position
                next_beat_position = start_beat + duration_beats
                
                # Debug output
                print(f"Debug: Note {segment['segment_number']} (MIDI {midi_note}): " 
                      f"start_beat={start_beat:.4f}, duration={duration_beats:.4f} beats")
                
                # Show original vs. continuous timing for comparison
                original_start = segment['start_beat']
                if abs(start_beat - original_start) > 0.001:  # Only show if meaningful difference
                    print(f"       (Original timing would be: start_beat={original_start:.4f})")
        
        # Pre-process all segments to calculate timing information
        print("\n==== PREPROCESSING SEGMENTS ====")
        all_segment_info = _preprocess_segment_pairs(all_segments, sample_rate, playback_tempo_enabled, 
                                                    source_bpm, target_bpm, beats_per_second)
        
        print(f"Debug: Found {len(all_segment_info)} segments for export (NO zero-length segments skipped)")
        
        # Detailed segment-to-MIDI mapping report
        print("\n==== SEGMENT TO MIDI MAPPING ====")
        print(f"Debug: Tempo: {tempo} BPM, beats per second: {beats_per_second}")
        
        for segment in all_segment_info:
            print(f"Debug: Segment {segment['segment_number']} (original {segment['index']+1}):")
            print(f"  - Samples: {segment['start_sample']} to {segment['end_sample']}")
            print(f"  - Time: {segment['start_time']:.3f}s to {segment['start_time']+segment['duration_seconds']:.3f}s "
                  f"(duration: {segment['duration_seconds']:.3f}s)")
            print(f"  - MIDI: start beat {segment['start_beat']:.3f}, duration {segment['duration_beats']:.3f} beats, "
                  f"MIDI note {segment['midi_note']}")
        
        print("\n==== GENERATING SEGMENTS ====")
        # Counter for actual exported segments
        segment_count = 0
        
        # List to store segment information for WAV files
        wavfile_segments = []
        
        for segment in all_segment_info:
            # Get segment information
            start = segment['start_sample']
            end = segment['end_sample']
            segment_count = segment['segment_number']
            
            print(f"Debug: Processing segment {segment_count} (original index {segment['index']+1}): {start} to {end}")
            
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

            # Add to SFZ content - reference the WAV file using the segment_filename
            sfz_content.append(f"""
<region>
sample={segment_filename}
pitch_keycenter={segment['midi_note']}
lokey={segment['midi_note']}
hikey={segment['midi_note']}
""")

            # Store info for debug output
            wavfile_segments.append({
                'filename': segment_filename,
                'path': segment_path,
                'midi_note': segment['midi_note'],
                'duration': segment['duration_seconds']
            })
            
            print(f"Debug: Segment {segment_count} exported: " 
                  f"start={segment['start_time']:.2f}s, duration={segment['duration_seconds']:.2f}s, "
                  f"note={segment['midi_note']}")
        
        # Apply continuous MIDI timing strategy
        _apply_continuous_note_timing(midi, all_segment_info)

        # MIDI file debug information
        print("\n==== MIDI EXPORT SUMMARY ====")
        print(f"Tempo: {midi.tempo} BPM")
        print(f"Time Signature: {midi.time_signature[0]}/{midi.time_signature[1]}")
        print(f"Total MIDI duration (beats): {midi.total_time:.2f}")
        print(f"Total MIDI duration (seconds): {midi.total_time / beats_per_second:.2f}")
        
        # Segment counts
        total_segments = len(all_segments)
        non_zero_segments = sum(1 for start_time, end_time in all_segments if start_time != end_time)
        zero_segments = total_segments - non_zero_segments
        
        print(f"\n==== SEGMENT STATISTICS ====")
        print(f"Total segments: {total_segments}")
        print(f"Total segments: {total_segments} (from SegmentManager)")
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
        print(f"Segments from SegmentManager: {all_segments}")
        print(f"Segments durations (seconds): {[end_time - start_time for start_time, end_time in all_segments]}")

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

        print(f"Exported {segment_count} segments, SFZ file, and MIDI file to {directory}")
        
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
