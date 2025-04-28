#!/usr/bin/env python3
"""
Segment Analyzer CLI - Analyze segment data from exported debug logs

This tool extracts segment data from export debug logs and analyzes them
to help debug segment count discrepancies.
"""

import os
import sys
import re
import argparse

# Add src directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(script_dir), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Now we can import our module
from python.utils.segment_analyzer import get_segment_report

def extract_segments_from_log(log_path):
    """Extract segments array from export log file"""
    with open(log_path, 'r') as f:
        content = f.read()
    
    # Look for segments array in the debug log
    segment_match = re.search(r'Segments array \(samples\): \[(.*?)\]', content)
    if not segment_match:
        return None, None
    
    segments_str = segment_match.group(1)
    segments = [int(x.strip()) for x in segments_str.split(',') if x.strip()]
    
    # Extract sample rate if available
    sample_rate_match = re.search(r'sample rate: (\d+) Hz', content)
    sample_rate = int(sample_rate_match.group(1)) if sample_rate_match else 44100
    
    return segments, sample_rate

def parse_segment_array(segment_array_str):
    """Parse a string representation of an array of integers"""
    # Strip brackets and split by commas
    segments_str = segment_array_str.strip('[]')
    segments = [int(x.strip()) for x in segments_str.split(',') if x.strip()]
    return segments

def main():
    parser = argparse.ArgumentParser(description='Analyze segment data from exported debug logs')
    
    # Create a mutually exclusive group for input methods
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--log', '-l', help='Path to export debug log file')
    input_group.add_argument('--segments', '-s', help='Segment array as string, e.g. "[0, 11025, 22050, 44100]"')
    
    parser.add_argument('--sample-rate', '-r', type=int, default=44100, 
                        help='Sample rate (required when using --segments, optional for --log)')
    
    args = parser.parse_args()
    
    # Process input based on provided arguments
    if args.log:
        segments, sample_rate = extract_segments_from_log(args.log)
        if not segments:
            print(f"Error: Could not find segments array in log file {args.log}")
            return 1
        
        print(f"Extracted segment data from log file {args.log}")
        sample_rate = sample_rate or args.sample_rate
    else:
        # Parse segments from command line
        try:
            segments = parse_segment_array(args.segments)
        except ValueError:
            print(f"Error: Could not parse segment array {args.segments}")
            return 1
        
        sample_rate = args.sample_rate
    
    # Generate and print the report
    report = get_segment_report(segments, sample_rate)
    print(report)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())