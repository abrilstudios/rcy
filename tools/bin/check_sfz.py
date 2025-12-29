#!/usr/bin/env python3
"""
SFZ Export Validation Utility

This utility analyzes and validates SFZ exports from RCY, checking:
- WAV file quality and specifications
- MIDI file content and tempo settings
- SFZ instrument mapping
- Tempo processing accuracy
- File consistency across the export

Usage:
    python bin/check_sfz.py <export_directory>
    
Example:
    python bin/check_sfz.py scratch/amen-test/
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to path for imports
script_dir = Path(__file__).parent
src_dir = script_dir.parent / 'src'
python_dir = src_dir / 'python'
sys.path.insert(0, str(python_dir))

try:
    import soundfile as sf
    from utils.midi_analyzer import analyze_midi
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you have soundfile installed: pip install soundfile")
    print("Make sure you're running from the RCY root directory")
    sys.exit(1)


def analyze_wav_files(export_dir):
    """Analyze all WAV files in the export directory."""
    wav_files = sorted([f for f in os.listdir(export_dir) if f.endswith('.wav')])
    
    if not wav_files:
        return None, "No WAV files found in export directory"
    
    print(f"📁 Found {len(wav_files)} WAV files")
    print("=" * 50)
    
    wav_analysis = []
    
    for wav_file in wav_files:
        wav_path = os.path.join(export_dir, wav_file)
        
        try:
            with sf.SoundFile(wav_path) as f:
                analysis = {
                    'filename': wav_file,
                    'sample_rate': f.samplerate,
                    'channels': f.channels,
                    'frames': len(f),
                    'duration': len(f) / f.samplerate,
                    'format': f.subtype,
                    'file_size': os.path.getsize(wav_path)
                }
                wav_analysis.append(analysis)
                
                print(f"🎵 {wav_file}:")
                print(f"   Sample Rate: {f.samplerate} Hz")
                print(f"   Channels: {f.channels}")
                print(f"   Duration: {analysis['duration']:.3f} seconds ({len(f)} frames)")
                print(f"   Format: {f.subtype}")
                print(f"   File Size: {analysis['file_size']:,} bytes")
                print()
                
        except Exception as e:
            return None, f"Error analyzing {wav_file}: {e}"
    
    return wav_analysis, None


def analyze_midi_file(export_dir):
    """Analyze MIDI file in the export directory."""
    midi_files = [f for f in os.listdir(export_dir) if f.endswith('.mid')]
    
    if not midi_files:
        return None, "No MIDI file found in export directory"
    
    if len(midi_files) > 1:
        return None, f"Multiple MIDI files found: {midi_files}"
    
    midi_file = midi_files[0]
    midi_path = os.path.join(export_dir, midi_file)
    
    try:
        result = analyze_midi(midi_path)
        
        print(f"🎼 MIDI File Analysis ({midi_file}):")
        print("=" * 50)
        print(f"   Tempo: {result['tempo']} BPM")
        print(f"   Time Signature: {result['time_signature'][0]}/{result['time_signature'][1]}")
        print(f"   Ticks per Beat: {result['ticks_per_beat']}")
        print(f"   Total Duration: {result['total_beats']:.2f} beats ({result['total_bars']:.2f} bars)")
        print(f"   Note Count: {result['note_count']}")
        print(f"   Note Pitches: {result['note_pitches']} (MIDI notes)")
        print()
        
        return result, None
        
    except Exception as e:
        return None, f"Error analyzing MIDI file {midi_file}: {e}"


def analyze_sfz_file(export_dir):
    """Analyze SFZ instrument file."""
    sfz_files = [f for f in os.listdir(export_dir) if f.endswith('.sfz')]
    
    if not sfz_files:
        return None, "No SFZ file found in export directory"
    
    if len(sfz_files) > 1:
        return None, f"Multiple SFZ files found: {sfz_files}"
    
    sfz_file = sfz_files[0]
    sfz_path = os.path.join(export_dir, sfz_file)
    
    try:
        with open(sfz_path, 'r') as f:
            content = f.read()
        
        # Parse regions
        regions = []
        current_region = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('<region>'):
                if current_region:
                    regions.append(current_region)
                current_region = {}
            elif '=' in line and current_region is not None:
                key, value = line.split('=', 1)
                current_region[key] = value
        
        if current_region:
            regions.append(current_region)
        
        print(f"🎹 SFZ Instrument File ({sfz_file}):")
        print("=" * 50)
        print(f"   Regions: {len(regions)}")
        
        for i, region in enumerate(regions, 1):
            sample = region.get('sample', 'N/A')
            pitch = region.get('pitch_keycenter', 'N/A')
            lokey = region.get('lokey', 'N/A')
            hikey = region.get('hikey', 'N/A')
            print(f"   Region {i}: {sample} → MIDI {pitch} (range: {lokey}-{hikey})")
        
        print()
        return regions, None
        
    except Exception as e:
        return None, f"Error analyzing SFZ file {sfz_file}: {e}"


def validate_export_consistency(wav_analysis, midi_analysis, sfz_regions):
    """Validate consistency across WAV, MIDI, and SFZ files."""
    print("✅ Export Consistency Validation:")
    print("=" * 50)
    
    issues = []
    
    # Check WAV file consistency
    if wav_analysis:
        sample_rates = set(w['sample_rate'] for w in wav_analysis)
        channels = set(w['channels'] for w in wav_analysis)
        formats = set(w['format'] for w in wav_analysis)
        
        if len(sample_rates) > 1:
            issues.append(f"❌ Inconsistent sample rates: {sample_rates}")
        else:
            print(f"✅ Sample Rate: {list(sample_rates)[0]} Hz (consistent)")
        
        if len(channels) > 1:
            issues.append(f"❌ Inconsistent channel counts: {channels}")
        else:
            print(f"✅ Channels: {list(channels)[0]} (consistent)")
        
        if len(formats) > 1:
            issues.append(f"❌ Inconsistent formats: {formats}")
        else:
            print(f"✅ Format: {list(formats)[0]} (consistent)")
    
    # Check WAV count vs MIDI notes vs SFZ regions
    wav_count = len(wav_analysis) if wav_analysis else 0
    midi_note_count = midi_analysis['note_count'] if midi_analysis else 0
    sfz_region_count = len(sfz_regions) if sfz_regions else 0
    
    if wav_count == midi_note_count == sfz_region_count:
        print(f"✅ File Count Consistency: {wav_count} WAV files = {midi_note_count} MIDI notes = {sfz_region_count} SFZ regions")
    else:
        issues.append(f"❌ File count mismatch: {wav_count} WAV ≠ {midi_note_count} MIDI ≠ {sfz_region_count} SFZ")
    
    # Check SFZ references actual WAV files
    if sfz_regions and wav_analysis:
        wav_filenames = set(w['filename'] for w in wav_analysis)
        sfz_samples = set(r.get('sample', '') for r in sfz_regions)
        
        missing_samples = sfz_samples - wav_filenames
        if missing_samples:
            issues.append(f"❌ SFZ references missing WAV files: {missing_samples}")
        else:
            print(f"✅ SFZ Sample References: All {len(sfz_samples)} samples found")
    
    # Check standard sample rate for professional compatibility
    if wav_analysis:
        standard_rates = {44100, 48000, 88200, 96000}
        actual_rate = wav_analysis[0]['sample_rate']
        if actual_rate in standard_rates:
            print(f"✅ Professional Sample Rate: {actual_rate} Hz")
        else:
            issues.append(f"⚠️  Non-standard sample rate: {actual_rate} Hz (consider 44100 or 48000)")
    
    print()
    return issues


def calculate_tempo_processing_accuracy(wav_analysis, midi_analysis):
    """Calculate and validate tempo processing accuracy."""
    if not wav_analysis or not midi_analysis:
        return
    
    print("🎯 Tempo Processing Analysis:")
    print("=" * 50)
    
    # Average WAV duration
    avg_duration = sum(w['duration'] for w in wav_analysis) / len(wav_analysis)
    midi_tempo = midi_analysis['tempo']
    
    print(f"   Average Segment Duration: {avg_duration:.3f} seconds")
    print(f"   MIDI Tempo: {midi_tempo} BPM")
    
    # Calculate expected duration for one beat at this tempo
    beat_duration = 60.0 / midi_tempo
    print(f"   Expected Beat Duration: {beat_duration:.3f} seconds")
    
    # Compare (assuming segments represent beats or fractions thereof)
    ratio = avg_duration / beat_duration
    print(f"   Duration Ratio: {ratio:.3f} (segment/beat)")
    
    if 0.9 <= ratio <= 1.1:
        print("   ✅ Tempo processing appears accurate (within 10%)")
    elif 0.4 <= ratio <= 0.6:
        print("   ✅ Segments appear to be half-beats (common for breakbeats)")
    elif 1.9 <= ratio <= 2.1:
        print("   ✅ Segments appear to be double-beats (common for slower material)")
    else:
        print(f"   ⚠️  Unusual tempo ratio - verify processing")
    
    print()


def main():
    parser = argparse.ArgumentParser(description='Validate RCY SFZ exports')
    parser.add_argument('export_dir', help='Path to export directory containing SFZ files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed analysis')
    
    args = parser.parse_args()
    
    export_dir = args.export_dir
    
    if not os.path.exists(export_dir):
        print(f"❌ Export directory not found: {export_dir}")
        sys.exit(1)
    
    if not os.path.isdir(export_dir):
        print(f"❌ Path is not a directory: {export_dir}")
        sys.exit(1)
    
    print(f"🔍 Analyzing SFZ export: {export_dir}")
    print("=" * 60)
    print()
    
    # Analyze WAV files
    wav_analysis, wav_error = analyze_wav_files(export_dir)
    if wav_error:
        print(f"❌ WAV Analysis Error: {wav_error}")
        return
    
    # Analyze MIDI file
    midi_analysis, midi_error = analyze_midi_file(export_dir)
    if midi_error:
        print(f"❌ MIDI Analysis Error: {midi_error}")
        return
    
    # Analyze SFZ file
    sfz_regions, sfz_error = analyze_sfz_file(export_dir)
    if sfz_error:
        print(f"❌ SFZ Analysis Error: {sfz_error}")
        return
    
    # Validate consistency
    issues = validate_export_consistency(wav_analysis, midi_analysis, sfz_regions)
    
    # Analyze tempo processing
    calculate_tempo_processing_accuracy(wav_analysis, midi_analysis)
    
    # Summary
    print("📋 Summary:")
    print("=" * 50)
    if not issues:
        print("🎉 All validations passed! Export is ready for use.")
    else:
        print("⚠️  Issues found:")
        for issue in issues:
            print(f"   {issue}")
    
    print()
    print("💡 This export can be used in:")
    print("   • Hardware samplers (SFZ format)")
    print("   • Software samplers (Kontakt, Battery, etc.)")
    print("   • DAWs with SFZ support")
    print("   • MIDI sequencers (using the .mid file)")


if __name__ == '__main__':
    main()