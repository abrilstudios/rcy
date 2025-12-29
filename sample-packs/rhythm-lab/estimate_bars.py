#!/usr/bin/env python3
"""Estimate bar counts for Rhythm Lab presets.

Uses duration and typical breakbeat BPM range (90-130) to estimate
whether each sample is 1, 2, or 4 bars.

Usage:
    python estimate_bars.py              # Analyze and update presets
    python estimate_bars.py --dry-run    # Preview without updating
    python estimate_bars.py --check      # Just show current vs estimated
"""

import argparse
import json
from pathlib import Path

import soundfile as sf

# Typical breakbeat BPM range
MIN_BPM = 85
MAX_BPM = 140

# Valid bar counts (prefer powers of 2)
VALID_BARS = [1, 2, 4, 8]


def estimate_bars(duration: float) -> tuple[int, float, str]:
    """
    Estimate bar count from duration.

    Returns (bars, estimated_bpm, confidence)
    """
    best_bars = 2
    best_bpm = 120.0
    best_error = float('inf')

    for bars in VALID_BARS:
        # bars = duration * bpm / 240 (4 beats per bar, 60 sec per min)
        # bpm = bars * 240 / duration
        bpm = bars * 240 / duration

        if MIN_BPM <= bpm <= MAX_BPM:
            # BPM is in valid range - check how "round" it is
            # Prefer BPMs close to common values (90, 100, 110, 120, etc.)
            nearest_10 = round(bpm / 10) * 10
            error = abs(bpm - nearest_10)

            if error < best_error:
                best_error = error
                best_bars = bars
                best_bpm = bpm

    # Confidence based on how clean the BPM is
    if best_error < 2:
        confidence = "high"
    elif best_error < 5:
        confidence = "medium"
    else:
        confidence = "low"

    return best_bars, best_bpm, confidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate bar counts for presets")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    parser.add_argument("--check", action="store_true", help="Just show analysis")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    presets_path = script_dir.parent.parent / "config" / "presets" / "rhythm-lab.json"

    # Load presets
    with open(presets_path) as f:
        presets = json.load(f)

    # All presets in this file are rl_ presets
    rl_presets = presets

    print(f"\nAnalyzing {len(rl_presets)} Rhythm Lab presets...\n")

    updates = []
    by_bars = {1: 0, 2: 0, 4: 0, 8: 0}

    for preset_id, preset in sorted(rl_presets.items()):
        filepath = script_dir.parent.parent / preset["filepath"]

        if not filepath.exists():
            continue

        try:
            info = sf.info(filepath)
            duration = info.duration
        except Exception:  # noqa: S112
            continue

        current_bars = preset.get("measures", 2)
        estimated_bars, estimated_bpm, confidence = estimate_bars(duration)

        by_bars[estimated_bars] = by_bars.get(estimated_bars, 0) + 1

        if current_bars != estimated_bars:
            updates.append({
                "id": preset_id,
                "name": preset.get("name", ""),
                "duration": duration,
                "current": current_bars,
                "estimated": estimated_bars,
                "bpm": estimated_bpm,
                "confidence": confidence,
            })

    # Report
    print("Distribution of estimated bars:")
    for bars in VALID_BARS:
        print(f"  {bars} bar(s): {by_bars.get(bars, 0)}")
    print()

    if not updates:
        print("All presets already have correct bar counts!")
        return

    print(f"Presets needing update: {len(updates)}\n")

    # Show updates grouped by confidence
    for conf in ["high", "medium", "low"]:
        conf_updates = [u for u in updates if u["confidence"] == conf]
        if conf_updates:
            print(f"[{conf.upper()} confidence] ({len(conf_updates)}):")
            for u in conf_updates[:10]:
                print(f"  {u['id']}: {u['current']} → {u['estimated']} bars "
                      f"({u['duration']:.2f}s, ~{u['bpm']:.0f} BPM)")
            if len(conf_updates) > 10:
                print(f"  ... and {len(conf_updates) - 10} more")
            print()

    if args.check:
        return

    if args.dry_run:
        print("Dry run - no changes made")
        return

    # Apply updates (only high/medium confidence)
    applied = 0
    for u in updates:
        if u["confidence"] in ("high", "medium"):
            presets[u["id"]]["measures"] = u["estimated"]
            applied += 1

    # Save
    with open(presets_path, "w") as f:
        json.dump(presets, f, indent=2)

    print(f"Updated {applied} presets (high/medium confidence only)")
    print(f"Skipped {len(updates) - applied} low-confidence estimates")


if __name__ == "__main__":
    main()
