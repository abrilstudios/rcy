#!/usr/bin/env python3
"""
MIDI Debug Tool - Analyze MIDI files and their relationship to segments

This script analyzes a MIDI file and its associated WAV segments to validate
consistency between the MIDI sequence and audio segments.
"""

import os
import sys
import argparse
from mido import MidiFile
import glob

def analyze_midi_notes(midi_path):
    """Analyze notes in a MIDI file"""
    try:
        midi_file = MidiFile(midi_path)
        
        notes = []
        time_sig = None
        tempo = None
        
        # Track cumulative time
        current_time = 0
        
        for track in midi_file.tracks:
            for msg in track:
                # Convert delta time to seconds
                current_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    # Note that we're tracking time in ticks, not seconds
                    notes.append({
                        'pitch': msg.note,
                        'time': current_time,
                        'velocity': msg.velocity
                    })
                elif msg.type == 'time_signature':
                    time_sig = (msg.numerator, msg.denominator)
                elif msg.type == 'set_tempo':
                    # Convert microseconds per beat to BPM
                    tempo = 60000000 / msg.tempo
        
        return {
            'notes': notes,
            'time_signature': time_sig,
            'tempo': tempo,
            'note_count': len(notes)
        }
    except Exception as e:
        print(f"Error analyzing MIDI file {midi_path}: {e}")
        return None

def count_segment_files(directory):
    """Count WAV segment files in directory"""
    segment_files = glob.glob(os.path.join(directory, "segment_*.wav"))
    return len(segment_files)

def main():
    parser = argparse.ArgumentParser(description='Debug MIDI files and segment consistency')
    # Add file parameter as an alternative to directory
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--directory', '-d', help='Directory containing MIDI and segment files')
    group.add_argument('--file', '-f', help='Path to a specific MIDI file')
    # Allow positional argument as alternative
    parser.add_argument('path', nargs='?', help='Path to MIDI file or directory containing MIDI files')
    args = parser.parse_args()
    
    # Determine if we're working with a file or directory
    # Priority: 1. Explicit --file flag, 2. Explicit --directory flag, 3. Positional argument
    if args.file:
        # Direct file path provided
        midi_path = args.file
        directory = os.path.dirname(midi_path)
    elif args.directory:
        # Directory path provided
        directory = args.directory
        midi_path = os.path.join(directory, "sequence.mid")
    elif args.path:
        # Check if positional argument is a file or directory
        if os.path.isfile(args.path):
            midi_path = args.path
            directory = os.path.dirname(midi_path)
        else:
            directory = args.path
            midi_path = os.path.join(directory, "sequence.mid")
    else:
        # This shouldn't happen due to required=True
        print("Error: No MIDI file or directory specified")
        parser.print_help()
        sys.exit(1)
    
    # Verify the MIDI file exists
    if not os.path.exists(midi_path):
        print(f"Error: MIDI file not found at {midi_path}")
        sys.exit(1)
    
    # Count segment files
    segment_count = count_segment_files(directory)
    
    # Analyze MIDI
    midi_info = analyze_midi_notes(midi_path)
    
    if not midi_info:
        sys.exit(1)
    
    # Print detailed information
    print("\n=== MIDI Debug Report ===")
    print(f"Directory: {directory}")
    print(f"MIDI file: {midi_path}")
    print(f"Time signature: {midi_info['time_signature']}")
    print(f"Tempo: {midi_info['tempo']:.2f} BPM")
    print(f"Total MIDI notes: {midi_info['note_count']}")
    print(f"WAV segment files: {segment_count}")
    
    # Check for consistency
    if midi_info['note_count'] != segment_count:
        print("\n⚠️ INCONSISTENCY DETECTED ⚠️")
        print(f"MIDI has {midi_info['note_count']} notes but found {segment_count} segment files")
        print("This suggests a mismatch between MIDI generation and audio export")
    else:
        print("\n✅ CONSISTENCY VERIFIED ✅")
        print(f"MIDI notes and segment files match ({segment_count})")
    
    # Print note details
    print("\nNote details:")
    for i, note in enumerate(midi_info['notes']):
        print(f"  Note {i+1}: pitch={note['pitch']} time={note['time']} velocity={note['velocity']}")
        
    # Calculate and print gaps between consecutive notes
    if len(midi_info['notes']) > 1 and midi_info['tempo']:
        # Open the MIDI file again to get ticks_per_beat
        midi_file = MidiFile(midi_path)
        ticks_per_beat = midi_file.ticks_per_beat
        seconds_per_beat = 60.0 / midi_info['tempo']
        seconds_per_tick = seconds_per_beat / ticks_per_beat
        
        print("\nTiming analysis:")
        print(f"Ticks per beat: {ticks_per_beat}")
        print(f"Seconds per beat: {seconds_per_beat:.6f}")
        print(f"Seconds per tick: {seconds_per_tick:.6f}")
        
        # Sort notes by time
        sorted_notes = sorted(midi_info['notes'], key=lambda x: x['time'])
        
        print("\nGaps between notes:")
        for i in range(1, len(sorted_notes)):
            prev_note_time = sorted_notes[i-1]['time']
            current_note_time = sorted_notes[i]['time']
            gap_ticks = current_note_time - prev_note_time
            gap_seconds = gap_ticks * seconds_per_tick
            gap_ms = gap_seconds * 1000
            
            print(f"  Gap between note {i} and {i+1}: {gap_ticks} ticks = {gap_seconds:.6f}s ({gap_ms:.2f}ms)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())