#!/usr/bin/env python3
"""
RX2 Marker Extractor

Extracts user-placed markers from RX2 files using the proven "non-standard unknown data" algorithm.
User markers are distinguished by having unknown data != 00000001 in SLCE chunks.
"""

import argparse
import json
import sys
import wave
from pathlib import Path

def extract_non_standard_unknown_markers(filepath):
    """Extract markers that have non-standard unknown data (not 00000001)"""
    
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return None
        
    # Find SLCL chunk
    slcl_pos = data.find(b'SLCL')
    if slcl_pos == -1:
        return None
    
    chunk_size = int.from_bytes(data[slcl_pos+4:slcl_pos+8], 'big')
    chunk_end = slcl_pos + 8 + chunk_size
    
    # Find markers with non-standard unknown data
    markers = []
    standard_unknown = bytes.fromhex('00000001')
    
    pos = slcl_pos + 8
    while pos < chunk_end:
        slce_pos = data.find(b'SLCE', pos)
        if slce_pos == -1 or slce_pos >= chunk_end:
            break
            
        if slce_pos + 20 <= len(data):
            slce_data = data[slce_pos:slce_pos+20]
            unknown_data = slce_data[12:16]
            ending_data = slce_data[16:20]
            
            # Check for non-standard unknown data
            if unknown_data != standard_unknown:
                sample_pos = int.from_bytes(slce_data[8:12], 'big')
                time_sec = sample_pos / 44100
                
                markers.append({
                    'sample_pos': sample_pos,
                    'time_sec': time_sec,
                    'unknown_data': unknown_data.hex(),
                    'ending_pattern': ending_data.hex()
                })
                
        pos = slce_pos + 4
    
    return sorted(markers, key=lambda x: x['time_sec'])

def analyze_source_audio(filepath):
    """Analyze source WAV file to get audio properties"""
    try:
        with wave.open(str(filepath), 'rb') as wav_file:
            frames = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            duration = frames / sample_rate
            
            return {
                'filename': Path(filepath).name,
                'duration': duration,
                'total_samples': frames,
                'sample_rate': sample_rate,
                'channels': channels,
                'bit_depth': sample_width * 8,
                'total_frames': frames
            }
    except Exception as e:
        print(f"Error reading source audio: {e}", file=sys.stderr)
        return None

def extract_rx2_audio_info(filepath):
    """Extract basic audio info from RX2 file (SDAT chunk)"""
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        # Find SDAT chunk
        sdat_pos = data.find(b'SDAT')
        if sdat_pos == -1:
            return None
        
        import struct
        sdat_size = struct.unpack('>I', data[sdat_pos+4:sdat_pos+8])[0]
        
        # Assume 16-bit stereo (standard for RX2)
        total_samples = sdat_size // 4
        duration = total_samples / 44100
        
        return {
            'filename': Path(filepath).name,
            'duration': duration,
            'total_samples': total_samples,
            'sample_rate': 44100,  # RX2 standard
            'channels': 2,         # RX2 standard
            'bit_depth': 16,       # RX2 standard
            'sdat_size': sdat_size
        }
    except Exception as e:
        print(f"Error reading RX2 audio info: {e}", file=sys.stderr)
        return None

def format_output(filepath, markers, output_format='human', source_info=None, rx2_info=None):
    """Format the output in requested format"""
    
    filename = Path(filepath).name
    
    if output_format == 'json':
        result = {
            'filename': filename,
            'user_markers': len(markers) if markers else 0,
            'markers': markers if markers else []
        }
        if source_info:
            result['source_audio'] = source_info
        if rx2_info:
            result['rx2_audio'] = rx2_info
        return json.dumps(result, indent=2)
    
    elif output_format == 'csv':
        if not markers:
            return f"{filename},0,,,,"
        
        lines = [f"{filename},{len(markers)},,,,"]
        for i, marker in enumerate(markers):
            lines.append(f",,{i+1},{marker['time_sec']:.3f},{marker['sample_pos']},{marker['ending_pattern']}")
        return "\n".join(lines)
    
    else:  # human-readable
        lines = [f"=== {filename} ==="]
        
        # Add audio info comparison if available
        if source_info and rx2_info:
            lines.append("\n--- Audio Comparison ---")
            lines.append(f"Source:  {source_info['duration']:.3f}s, {source_info['total_samples']} samples, {source_info['sample_rate']}Hz, {source_info['channels']}ch, {source_info['bit_depth']}bit")
            lines.append(f"RX2:     {rx2_info['duration']:.3f}s, {rx2_info['total_samples']} samples, {rx2_info['sample_rate']}Hz, {rx2_info['channels']}ch, {rx2_info['bit_depth']}bit")
            
            # Sanity checks
            duration_diff = abs(source_info['duration'] - rx2_info['duration'])
            sample_diff = abs(source_info['total_samples'] - rx2_info['total_samples'])
            
            if duration_diff < 0.001 and sample_diff == 0:
                lines.append("✅ Audio properties match perfectly")
            else:
                lines.append(f"⚠️  Audio mismatch: duration diff {duration_diff:.3f}s, sample diff {sample_diff}")
        
        elif rx2_info:
            lines.append(f"\n--- RX2 Audio Info ---")
            lines.append(f"Duration: {rx2_info['duration']:.3f}s, Samples: {rx2_info['total_samples']}, Rate: {rx2_info['sample_rate']}Hz")
        
        lines.append(f"\n--- User Markers ---")
        lines.append(f"User markers found: {len(markers) if markers else 0}")
        
        if markers:
            lines.append("\nMarker positions:")
            for i, marker in enumerate(markers):
                lines.append(f"  {i+1}. {marker['time_sec']:.3f}s (sample: {marker['sample_pos']}, pattern: {marker['ending_pattern']})")
        else:
            lines.append("No user markers detected")
        
        return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Extract user-placed markers from RX2 files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s file.rx2                    # Human-readable output
  %(prog)s file.rx2 --json             # JSON output
  %(prog)s file.rx2 --csv              # CSV output
  %(prog)s *.rx2 --quiet               # Process multiple files quietly
        """
    )
    
    parser.add_argument('files', nargs='+', help='RX2 file(s) to process')
    
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument('--json', action='store_true', 
                            help='Output in JSON format')
    output_group.add_argument('--csv', action='store_true',
                            help='Output in CSV format')
    
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress error messages for missing files')
    
    parser.add_argument('--summary', action='store_true',
                       help='Show summary statistics at end')
    
    parser.add_argument('--source', type=str,
                       help='Source WAV file for audio comparison and validation')
    
    args = parser.parse_args()
    
    # Determine output format
    if args.json:
        output_format = 'json'
    elif args.csv:
        output_format = 'csv'
    else:
        output_format = 'human'
    
    # CSV header
    if output_format == 'csv':
        print("filename,user_markers,marker_index,time_seconds,sample_position,ending_pattern")
    
    # Analyze source audio if provided
    source_info = None
    if args.source:
        source_info = analyze_source_audio(args.source)
        if source_info is None:
            print(f"Error: Could not read source file {args.source}", file=sys.stderr)
            sys.exit(1)
    
    # Process files
    total_files = 0
    successful_files = 0
    total_markers = 0
    
    for file_pattern in args.files:
        # Handle glob patterns
        if '*' in file_pattern or '?' in file_pattern:
            from glob import glob
            files = glob(file_pattern)
        else:
            files = [file_pattern]
        
        for filepath in files:
            total_files += 1
            
            markers = extract_non_standard_unknown_markers(filepath)
            
            if markers is None:
                if not args.quiet:
                    print(f"Error: Could not read {filepath}", file=sys.stderr)
                continue
            
            successful_files += 1
            total_markers += len(markers)
            
            # Get RX2 audio info for comparison
            rx2_info = extract_rx2_audio_info(filepath)
            
            output = format_output(filepath, markers, output_format, source_info, rx2_info)
            print(output)
            
            # Add spacing between files in human format
            if output_format == 'human' and len(args.files) > 1:
                print()
    
    # Summary
    if args.summary:
        print(f"\n=== SUMMARY ===", file=sys.stderr)
        print(f"Files processed: {successful_files}/{total_files}", file=sys.stderr)
        print(f"Total markers found: {total_markers}", file=sys.stderr)
        if successful_files > 0:
            print(f"Average markers per file: {total_markers/successful_files:.1f}", file=sys.stderr)

if __name__ == "__main__":
    main()