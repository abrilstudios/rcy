#!/usr/bin/env python3
"""Generate RCY presets from downloaded Rhythm Lab WAV files.

Scans the audio/ directory for WAV files and generates preset entries
in presets/presets.json.

Usage:
    python generate_presets.py              # Generate all presets
    python generate_presets.py --dry-run    # Preview without writing
    python generate_presets.py --list       # List existing rl_ presets
"""

import json
import re
from pathlib import Path


def slugify(text: str, max_length: int = 40) -> str:
    """Convert text to a URL-safe slug."""
    # Lowercase
    slug = text.lower()
    # Replace common separators with underscore
    slug = re.sub(r"[\s\-]+", "_", slug)
    # Remove special characters except underscore
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    # Collapse multiple underscores
    slug = re.sub(r"_+", "_", slug)
    # Strip leading/trailing underscores
    slug = slug.strip("_")
    # Truncate
    return slug[:max_length]


def parse_filename(filename: str) -> tuple[str, str]:
    """Parse 'Artist - Title.wav' into (artist, title)."""
    name = filename.rsplit(".", 1)[0]  # Remove extension

    if " - " in name:
        parts = name.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()

    # Fallback: use whole name as title
    return "Unknown", name.strip()


def generate_preset_id(title: str, existing_ids: set) -> str:
    """Generate a unique preset ID."""
    base_slug = slugify(title)
    preset_id = f"rl_{base_slug}"

    if preset_id not in existing_ids:
        return preset_id

    # Handle duplicates with suffix
    counter = 2
    while f"{preset_id}_{counter}" in existing_ids:
        counter += 1

    return f"{preset_id}_{counter}"


def load_presets(presets_path: Path) -> dict:
    """Load existing presets."""
    if presets_path.exists():
        with open(presets_path) as f:
            return json.load(f)
    return {}


def save_presets(presets: dict, presets_path: Path) -> None:
    """Save presets to file."""
    with open(presets_path, "w") as f:
        json.dump(presets, f, indent=2)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate RCY presets from Rhythm Lab WAVs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--list", action="store_true", help="List existing rl_ presets")
    args = parser.parse_args()

    # Paths
    script_dir = Path(__file__).parent
    audio_dir = script_dir / "audio"
    presets_path = script_dir.parent.parent / "presets" / "presets.json"

    # Load existing presets
    presets = load_presets(presets_path)

    if args.list:
        rl_presets = {k: v for k, v in presets.items() if k.startswith("rl_")}
        print(f"\nExisting Rhythm Lab presets ({len(rl_presets)}):\n")
        for pid, data in sorted(rl_presets.items()):
            print(f"  {pid}: {data.get('name', 'Unknown')}")
        return

    # Find WAV files
    wav_files = sorted(audio_dir.glob("*.wav"))
    if not wav_files:
        print("No WAV files found in audio/ directory.")
        print("Download the archive from rhythm-lab.com and extract to audio/")
        return

    print(f"\nRhythm Lab Preset Generator")
    print(f"===========================")
    print(f"Found {len(wav_files)} WAV files in audio/")
    print()

    # Remove old rl_ presets (we'll regenerate them all)
    non_rl_presets = {k: v for k, v in presets.items() if not k.startswith("rl_")}
    print(f"Keeping {len(non_rl_presets)} non-Rhythm Lab presets")

    # Generate new presets
    new_presets = dict(non_rl_presets)
    existing_ids = set(new_presets.keys())
    generated = 0

    for wav_path in wav_files:
        filename = wav_path.name
        artist, title = parse_filename(filename)
        preset_id = generate_preset_id(title, existing_ids)
        existing_ids.add(preset_id)

        rel_path = f"sample-packs/rhythm-lab/audio/{filename}"

        new_presets[preset_id] = {
            "filepath": rel_path,
            "name": f"{artist} - {title}",
            "artist": artist,
            "measures": 2  # Default; adjust manually for known breaks
        }
        generated += 1

        if args.dry_run and generated <= 10:
            print(f"  {preset_id}: {artist} - {title}")

    if args.dry_run:
        if generated > 10:
            print(f"  ... and {generated - 10} more")
        print(f"\nWould generate {generated} presets (dry run)")
        return

    # Save updated presets
    save_presets(new_presets, presets_path)

    print(f"Generated {generated} Rhythm Lab presets")
    print(f"Total presets: {len(new_presets)}")
    print(f"\nUpdated: {presets_path}")
    print("\nUse 'just run' and '/presets' to see all available presets.")


if __name__ == "__main__":
    main()
