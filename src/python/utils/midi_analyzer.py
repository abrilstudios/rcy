"""
MIDI Analyzer - Utility to analyze MIDI files for tempo and bar information

This tool analyzes MIDI files and provides information about tempo, time signature,
and number of bars in the sequence.

Part of the RCY (Recycling) audio tool suite.
"""

import argparse
import os
import logging
from typing import Any
import mido

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def analyze_midi(midi_path: str) -> dict[str, Any]:
    """
    Analyze a MIDI file and extract tempo, bar information, and notes.
    
    Args:
        midi_path: Path to the MIDI file
        
    Returns:
        Dict containing analysis results
    """
    mid = mido.MidiFile(midi_path)
    
    # Initialize variables
    ticks_per_beat = mid.ticks_per_beat
    tempo = None
    time_signature = None
    total_ticks = 0
    notes = []
    
    # Scan for tempo, time signature, and notes
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo = mido.tempo2bpm(msg.tempo)
            elif msg.type == 'time_signature':
                time_signature = (msg.numerator, msg.denominator)
            elif msg.type == 'note_on' and msg.velocity > 0:
                notes.append(msg.note)
    
    # Calculate total length
    for track in mid.tracks:
        track_ticks = 0
        for msg in track:
            track_ticks += msg.time
        total_ticks = max(total_ticks, track_ticks)
    
    # Calculate bars
    if time_signature:
        # Beats per bar
        beats_per_bar = 4 * time_signature[0] / time_signature[1]
        total_beats = total_ticks / ticks_per_beat
        total_bars = total_beats / beats_per_bar
    else:
        # Assume 4/4 time signature if not specified
        total_beats = total_ticks / ticks_per_beat
        total_bars = total_beats / 4
    
    return {
        'ticks_per_beat': ticks_per_beat,
        'tempo': tempo,
        'time_signature': time_signature,
        'total_ticks': total_ticks,
        'total_beats': total_beats,
        'total_bars': total_bars,
        'note_count': len(notes),
        'note_pitches': sorted(notes)
    }


def main() -> int:
    """Main entry point for the MIDI analyzer tool."""
    parser = argparse.ArgumentParser(description="Analyze MIDI files for tempo and bar information")
    parser.add_argument("-i", "--input", help="Input MIDI file to analyze")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    # If no input file is provided, show help and exit
    if not args.input:
        parser.print_help()
        print("\nExamples:")
        print("  Analyze a MIDI file:")
        print("    midi-analyzer -i /path/to/sequence.mid")
        return 0
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    midi_path = args.input
    
    # Validate input file
    if not os.path.exists(midi_path):
        logger.error(f"Input file '{midi_path}' does not exist.")
        return 1
    
    if not os.path.isfile(midi_path):
        logger.error(f"Input path '{midi_path}' is not a file.")
        return 1
    
    try:
        # Analyze the MIDI file
        logger.info(f"Analyzing MIDI file: {midi_path}")
        result = analyze_midi(midi_path)
        
        # Display results
        print(f"\nMIDI File Analysis: {os.path.basename(midi_path)}")
        print(f"============================================")
        print(f"Ticks per beat: {result['ticks_per_beat']}")
        
        if result['tempo']:
            print(f"Tempo: {result['tempo']:.2f} BPM")
        else:
            print("Tempo: Not specified")
        
        if result['time_signature']:
            print(f"Time Signature: {result['time_signature'][0]}/{result['time_signature'][1]}")
        else:
            print("Time Signature: Not specified (assuming 4/4)")
        
        print(f"Total ticks: {result['total_ticks']}")
        print(f"Total beats: {result['total_beats']:.2f}")
        print(f"Total bars: {result['total_bars']:.2f}")
        print(f"Note count: {result['note_count']}")
        
        if args.verbose and result['note_count'] > 0:
            print(f"Note pitches: {result['note_pitches']}")
        
        logger.info("Analysis complete")
        return 0
        
    except Exception as e:
        logger.error(f"Error analyzing MIDI file: {e}")
        return 1


if __name__ == "__main__":
    exit(main())