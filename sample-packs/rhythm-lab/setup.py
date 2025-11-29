#!/usr/bin/env python3
"""Setup script for Rhythm Lab breakbeats sample pack.

Downloads audio files from rhythm-lab.com and creates RCY presets.

Usage:
    python setup.py              # Download all and create presets
    python setup.py --list       # List available breakbeats
    python setup.py --id amen    # Download specific breakbeat by ID pattern
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path


def load_manifest():
    """Load the manifest file."""
    manifest_path = Path(__file__).parent / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def load_presets():
    """Load the main presets file."""
    presets_path = Path(__file__).parent.parent.parent / "presets" / "presets.json"
    if presets_path.exists():
        with open(presets_path) as f:
            return json.load(f)
    return {}


def save_presets(presets):
    """Save the main presets file."""
    presets_path = Path(__file__).parent.parent.parent / "presets" / "presets.json"
    with open(presets_path, 'w') as f:
        json.dump(presets, f, indent=2)
    print(f"Updated {presets_path}")


def get_download_url(filename):
    """Construct download URL for a breakbeat file."""
    # rhythm-lab.com uses URL-encoded filenames in various date directories
    # We'll try common patterns
    encoded = urllib.parse.quote(filename)
    base_urls = [
        f"https://rhythm-lab.com/sstorage/53/2015/02/{encoded}",
        f"https://rhythm-lab.com/sstorage/53/2015/03/{encoded}",
        f"https://rhythm-lab.com/sstorage/53/2025/07/{encoded}",
    ]
    return base_urls


def download_file(url, dest_path):
    """Download a file from URL to destination path."""
    try:
        print(f"  Downloading from {url}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(dest_path, 'wb') as f:
                f.write(response.read())
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        print(f"  HTTP error: {e}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def download_breakbeat(breakbeat, audio_dir):
    """Download a single breakbeat file."""
    filename = breakbeat['filename']
    dest_path = audio_dir / filename

    if dest_path.exists():
        print(f"  Already exists: {filename}")
        return True

    urls = get_download_url(filename)
    for url in urls:
        if download_file(url, dest_path):
            print(f"  Downloaded: {filename}")
            return True

    print(f"  FAILED to download: {filename}")
    return False


def create_preset(breakbeat, audio_dir, presets):
    """Create an RCY preset for a breakbeat."""
    preset_id = f"rl_{breakbeat['id']}"
    filename = breakbeat['filename']
    audio_path = audio_dir / filename

    if not audio_path.exists():
        return False

    # Use relative path from project root
    rel_path = f"sample-packs/rhythm-lab/audio/{filename}"

    presets[preset_id] = {
        "filepath": rel_path,
        "name": f"{breakbeat['artist']} - {breakbeat['title']}",
        "artist": breakbeat['artist'],
        "measures": breakbeat.get('measures', 2)
    }
    return True


def list_breakbeats():
    """List all available breakbeats."""
    manifest = load_manifest()
    print(f"\n{manifest['name']}")
    print(f"Source: {manifest['source']}")
    print(f"\nAvailable breakbeats ({len(manifest['breakbeats'])}):\n")

    for bb in manifest['breakbeats']:
        print(f"  {bb['id']:25} {bb['artist']} - {bb['title']}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Setup Rhythm Lab breakbeats')
    parser.add_argument('--list', action='store_true', help='List available breakbeats')
    parser.add_argument('--id', type=str, help='Download specific breakbeat(s) matching ID pattern')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be downloaded')
    args = parser.parse_args()

    if args.list:
        list_breakbeats()
        return

    manifest = load_manifest()
    audio_dir = Path(__file__).parent / "audio"
    audio_dir.mkdir(exist_ok=True)

    # Filter breakbeats if --id specified
    breakbeats = manifest['breakbeats']
    if args.id:
        breakbeats = [bb for bb in breakbeats if args.id.lower() in bb['id'].lower()]
        if not breakbeats:
            print(f"No breakbeats matching '{args.id}'")
            return

    print(f"\n{manifest['name']}")
    print(f"Processing {len(breakbeats)} breakbeats...\n")

    if args.dry_run:
        for bb in breakbeats:
            print(f"  Would download: {bb['filename']}")
        return

    # Download and create presets
    presets = load_presets()
    downloaded = 0
    created = 0

    for bb in breakbeats:
        print(f"\n[{bb['id']}] {bb['artist']} - {bb['title']}")

        if download_breakbeat(bb, audio_dir):
            downloaded += 1
            if create_preset(bb, audio_dir, presets):
                created += 1

    # Save updated presets
    if created > 0:
        save_presets(presets)

    print(f"\n\nSummary:")
    print(f"  Downloaded: {downloaded}/{len(breakbeats)}")
    print(f"  Presets created: {created}")
    print(f"\nUse 'just tui' and '/presets' to see all available presets.")


if __name__ == '__main__':
    main()
