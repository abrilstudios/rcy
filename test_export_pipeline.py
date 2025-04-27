#!/usr/bin/env python3
"""
Test script for the audio export pipeline
- Loads preset audio
- Sets playback tempo
- Processes segments
- Exports slices to a temporary directory
- Prints information about exported files
"""
import os
import tempfile
import sys
import numpy as np
import soundfile as sf

# Add src/python to path
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'python')
sys.path.append(src_dir)

from audio_processor import WavAudioProcessor
from export_utils import ExportUtils
from config_manager import config

def main():
    # Create temporary directory for exports
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Temporary export directory: {temp_dir}")
        
        # Load preset
        model = WavAudioProcessor(preset_id='amen_classic')
        print(f"Loaded preset: amen_classic")
        print(f"Source BPM: {model.source_bpm:.2f}")
        print(f"Original sample rate: {model.sample_rate} Hz")
        
        # Generate some segments (by time)
        total_samples = len(model.data_left)
        # Create segments every 0.25 seconds
        quarter_sec_samples = int(0.25 * model.sample_rate)
        segments = list(range(0, total_samples, quarter_sec_samples))
        model.segments = segments
        print(f"Created {len(segments)} segments")
        
        # Set playback tempo (1.5x speed)
        target_bpm = int(model.source_bpm * 1.5)
        model.set_playback_tempo(True, target_bpm)
        print(f"Set target BPM to {target_bpm} (1.5x)")
        
        # Turn on tail fade (just for display - the actual value is read from the config file)
        td_config = {"enabled": True, "durationMs": 30, "curve": "exponential"}
        # We'll manually read the current config for display
        current_config = config.get_setting("audio", "tailFade", {})
        print(f"Tail fade config: enabled={current_config.get('enabled', False)}, " 
              f"duration={current_config.get('durationMs', 10)}ms, "
              f"curve={current_config.get('curve', 'linear')}")
        
        # Export segments
        print("Exporting segments...")
        tempo = model.get_tempo(4)  # 4 measures
        ExportUtils.export_segments(model, tempo, 4, temp_dir)
        
        # List exported files
        files = os.listdir(temp_dir)
        wav_files = [f for f in files if f.endswith('.wav')]
        print(f"Exported {len(wav_files)} WAV files")
        
        # Check first exported segment
        if wav_files:
            first_file = os.path.join(temp_dir, wav_files[0])
            with sf.SoundFile(first_file) as sound_file:
                print(f"\nExported file info ({wav_files[0]}):")
                print(f"Sample rate: {sound_file.samplerate} Hz")
                print(f"Duration: {len(sound_file) / sound_file.samplerate:.4f} seconds")
                print(f"Channels: {sound_file.channels}")
                
                # Verify the sample rate is the standard rate (44100 Hz)
                if sound_file.samplerate == model.sample_rate:
                    print(f"\n✅ SUCCESS: Exported file has standard sample rate: {sound_file.samplerate} Hz")
                else:
                    print(f"\n❌ ERROR: Sample rate is not standard: {sound_file.samplerate} Hz")
                
                # The pitch adjustment is now preserved in the audio content
                # rather than in the sample rate, so we can't directly verify it
                # Just show the expected ratio for reference
                expected_ratio = target_bpm / model.source_bpm
                print(f"Tempo ratio applied during processing: {expected_ratio:.4f}x")

if __name__ == "__main__":
    main()