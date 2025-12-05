#!/usr/bin/env python3
"""Slow download script for Rhythm Lab breakbeats.

Downloads missing files with a delay between each to avoid rate limiting.

Usage:
    python download_slow.py              # Download all missing (10s delay)
    python download_slow.py --delay 15   # Use 15s delay
    python download_slow.py --dry-run    # Show what would be downloaded
    python download_slow.py --limit 5    # Download only first 5 missing
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path


def load_manifest():
    """Load the manifest file."""
    manifest_path = Path(__file__).parent / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def get_download_urls(filename):
    """Construct possible download URLs for a breakbeat file."""
    encoded = urllib.parse.quote(filename)
    # Try various date directories used by rhythm-lab.com
    base_urls = [
        f"https://rhythm-lab.com/sstorage/53/2015/02/{encoded}",
        f"https://rhythm-lab.com/sstorage/53/2015/03/{encoded}",
        f"https://rhythm-lab.com/sstorage/53/2014/12/{encoded}",
        f"https://rhythm-lab.com/sstorage/53/2014/11/{encoded}",
        f"https://rhythm-lab.com/sstorage/53/2025/07/{encoded}",
    ]
    return base_urls


def download_file(url, dest_path, timeout=30):
    """Download a file from URL to destination path."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read()
            # Verify it's actually audio (WAV starts with RIFF)
            if not content.startswith(b'RIFF'):
                return False, "Not a WAV file"
            with open(dest_path, 'wb') as f:
                f.write(content)
        return True, None
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL error: {e.reason}"
    except Exception as e:
        return False, str(e)


def get_missing_breakbeats(manifest, audio_dir):
    """Get list of breakbeats that haven't been downloaded."""
    existing = set(f.name for f in audio_dir.glob('*.wav'))
    missing = []
    for bb in manifest['breakbeats']:
        if bb['filename'] not in existing:
            missing.append(bb)
    return missing


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Slowly download Rhythm Lab breakbeats')
    parser.add_argument('--delay', type=int, default=10, help='Seconds between downloads (default: 10)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be downloaded')
    parser.add_argument('--limit', type=int, help='Limit number of downloads')
    parser.add_argument('--timeout', type=int, default=30, help='Download timeout in seconds')
    args = parser.parse_args()

    manifest = load_manifest()
    audio_dir = Path(__file__).parent / "audio"
    audio_dir.mkdir(exist_ok=True)

    missing = get_missing_breakbeats(manifest, audio_dir)

    if not missing:
        print("All breakbeats already downloaded!")
        return

    if args.limit:
        missing = missing[:args.limit]

    print(f"\nRhythm Lab Breakbeats - Slow Download")
    print(f"======================================")
    print(f"Missing: {len(missing)} files")
    print(f"Delay: {args.delay}s between downloads")
    print()

    if args.dry_run:
        for bb in missing:
            print(f"  Would download: {bb['filename']}")
        return

    downloaded = 0
    failed = []

    for i, bb in enumerate(missing):
        filename = bb['filename']
        dest_path = audio_dir / filename

        print(f"[{i+1}/{len(missing)}] {bb['artist']} - {bb['title']}")
        print(f"  File: {filename}")

        urls = get_download_urls(filename)
        success = False

        for url in urls:
            print(f"  Trying: {url[:60]}...")
            ok, err = download_file(url, dest_path, timeout=args.timeout)
            if ok:
                size = dest_path.stat().st_size
                print(f"  OK: {size:,} bytes")
                downloaded += 1
                success = True
                break
            else:
                print(f"  Failed: {err}")

        if not success:
            failed.append(bb)
            print(f"  FAILED - could not download from any URL")

        # Delay before next download (except after last one)
        if i < len(missing) - 1:
            print(f"  Waiting {args.delay}s...")
            time.sleep(args.delay)

        print()

    print(f"\nSummary")
    print(f"=======")
    print(f"Downloaded: {downloaded}/{len(missing)}")

    if failed:
        print(f"\nFailed downloads ({len(failed)}):")
        for bb in failed:
            print(f"  - {bb['filename']}")

    if downloaded > 0:
        print(f"\nRun 'python setup.py' to create presets for downloaded files.")


if __name__ == '__main__':
    main()
