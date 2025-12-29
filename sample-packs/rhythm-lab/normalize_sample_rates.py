#!/usr/bin/env python3
"""Normalize all WAV files to 44100 Hz sample rate.

Scans the audio/ directory and resamples any files not at 44100 Hz.
Uses librosa for high-quality resampling.

Usage:
    python normalize_sample_rates.py              # Convert all
    python normalize_sample_rates.py --dry-run    # Preview only
    python normalize_sample_rates.py --check      # Just check sample rates
"""

import argparse
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

TARGET_SAMPLE_RATE = 44100


def check_sample_rate(wav_path: Path) -> tuple[int | None, str | None]:
    """Check sample rate of a WAV file. Returns (rate, error)."""
    try:
        info = sf.info(wav_path)
        return info.samplerate, None
    except Exception as e:
        return None, str(e)


def resample_file(wav_path: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Resample a file to 44100 Hz. Returns (success, message)."""
    rate, error = check_sample_rate(wav_path)

    if error:
        return False, f"Cannot read: {error}"

    if rate == TARGET_SAMPLE_RATE:
        return True, "Already 44100 Hz"

    if dry_run:
        return True, f"Would convert from {rate} Hz"

    try:
        # Load with original sample rate
        audio, orig_sr = librosa.load(wav_path, sr=None, mono=False)

        # Resample to 44100
        if audio.ndim == 1:
            # Mono
            resampled = librosa.resample(audio, orig_sr=orig_sr, target_sr=TARGET_SAMPLE_RATE)
        else:
            # Stereo - resample each channel
            resampled = np.array([
                librosa.resample(audio[0], orig_sr=orig_sr, target_sr=TARGET_SAMPLE_RATE),
                librosa.resample(audio[1], orig_sr=orig_sr, target_sr=TARGET_SAMPLE_RATE)
            ])

        # Write back (transpose for soundfile if stereo)
        if resampled.ndim == 2:
            resampled = resampled.T

        sf.write(wav_path, resampled, TARGET_SAMPLE_RATE)
        return True, f"Converted from {orig_sr} Hz"

    except Exception as e:
        return False, f"Conversion failed: {e}"


def main():
    parser = argparse.ArgumentParser(description="Normalize WAV files to 44100 Hz")
    parser.add_argument("--dry-run", action="store_true", help="Preview without converting")
    parser.add_argument("--check", action="store_true", help="Just check sample rates")
    args = parser.parse_args()

    audio_dir = Path(__file__).parent / "audio"

    if not audio_dir.exists():
        print("No audio/ directory found")
        sys.exit(1)

    wav_files = sorted(audio_dir.glob("*.wav"))
    print(f"\nScanning {len(wav_files)} WAV files...\n")

    non_44100 = []
    corrupted = []
    converted = []
    failed = []

    for wav in wav_files:
        rate, error = check_sample_rate(wav)

        if error:
            corrupted.append((wav.name, error))
            continue

        if rate != TARGET_SAMPLE_RATE:
            non_44100.append((wav.name, rate))

            if not args.check:
                success, msg = resample_file(wav, dry_run=args.dry_run)
                if success:
                    converted.append((wav.name, msg))
                else:
                    failed.append((wav.name, msg))

    # Report
    if args.check:
        print(f"Files at 44100 Hz: {len(wav_files) - len(non_44100) - len(corrupted)}")
        print(f"Files needing conversion: {len(non_44100)}")
        for name, rate in non_44100:
            print(f"  {rate} Hz: {name}")
        if corrupted:
            print(f"\nCorrupted files: {len(corrupted)}")
            for name, error in corrupted:
                print(f"  {name}: {error}")
    else:
        if converted:
            print(f"{'Would convert' if args.dry_run else 'Converted'}: {len(converted)}")
            for name, msg in converted:
                print(f"  {name}: {msg}")

        if failed:
            print(f"\nFailed: {len(failed)}")
            for name, msg in failed:
                print(f"  {name}: {msg}")

        if corrupted:
            print(f"\nCorrupted (need re-extraction from archive): {len(corrupted)}")
            for name, error in corrupted[:5]:
                print(f"  {name}")
            if len(corrupted) > 5:
                print(f"  ... and {len(corrupted) - 5} more")

    if failed or corrupted:
        sys.exit(1)


if __name__ == "__main__":
    main()
