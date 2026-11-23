"""Akai S2800 hardware integration tests.

Progressive tests that verify real device communication, ordered from
simplest to most complex. Each test mirrors a proven operation from
the old s5000 CLI (tools/bin/s5000).

Run:  pytest -m s2800 tests/test_s2800.py

Requires S2800 connected via MIDI (Volt 2 interface).
"""

import time

import numpy as np
import pytest

from s2800 import S2800
from s2800.sampler import S2800Error

pytestmark = pytest.mark.s2800


# --- Fixtures ---

@pytest.fixture
def sampler():
    """Provide a connected S2800."""
    s = S2800()
    s.open()
    yield s
    s.close()


def _short_pcm(duration_s: float = 0.05, freq: float = 440.0,
               sample_rate: int = 44100) -> bytes:
    """Generate a short sine as signed 16-bit PCM."""
    n = int(sample_rate * duration_s)
    t = np.linspace(0, 2 * np.pi * freq * duration_s, n, dtype=np.float32)
    return (np.sin(t) * 0.8 * 32767).astype(np.int16).tobytes()


# --- Tests (progressive order) ---

def test_find_ports():
    """Auto-detection should find the S2800 MIDI ports."""
    all_in, all_out = S2800.list_ports()
    print(f"\nAll MIDI inputs:  {all_in}")
    print(f"All MIDI outputs: {all_out}")

    found_in, found_out = S2800.find_ports()
    print(f"Auto-detected in:  {found_in}")
    print(f"Auto-detected out: {found_out}")

    assert found_in is not None, f"No input port found. Available: {all_in}"
    assert found_out is not None, f"No output port found. Available: {all_out}"


def test_connect(sampler):
    """Opening ports to the S2800 should succeed."""
    # If we got here, the fixture opened ports successfully.
    assert sampler._port_in is not None
    assert sampler._port_out is not None


def test_hello(sampler):
    """Send RSLIST, get any SLIST response. Simplest alive check."""
    # This is the proven "say hi": F0 47 00 04 48 F7
    # Any response starting with func=0x05 means the device is talking.
    result = sampler.list_samples()
    assert isinstance(result, list)


def test_list_samples_returns_names(sampler):
    """Sample list entries should be non-empty strings."""
    names = sampler.list_samples()
    for name in names:
        assert isinstance(name, str)
        assert len(name) > 0


def test_upload_and_verify(sampler):
    """Upload a short sample, verify it appears in the list."""
    pcm = _short_pcm(0.05)
    before = sampler.list_samples()

    idx = sampler.upload_sample(pcm, 44100, "TEST SINE")
    time.sleep(0.3)

    after = sampler.list_samples()
    assert len(after) == len(before) + 1
    assert "TEST SINE" in after


def test_delete_and_verify(sampler):
    """Upload then delete a sample, verify count drops by 1."""
    # Start clean
    sampler.delete_all_samples()
    time.sleep(1.0)

    pcm = _short_pcm(0.05)
    idx = sampler.upload_sample(pcm, 44100, "DEL TEST")
    time.sleep(0.5)
    after_upload = sampler.list_samples()
    assert len(after_upload) == 1, f"Expected 1 sample, got {after_upload}"

    sampler.delete_sample(idx)
    time.sleep(1.0)
    after_delete = sampler.list_samples()
    assert len(after_delete) == 0, f"Expected 0 samples, got {after_delete}"


def test_delete_all(sampler):
    """delete_all_samples should leave the device empty."""
    # Upload something so there's at least one sample to delete
    pcm = _short_pcm(0.05)
    sampler.upload_sample(pcm, 44100, "DELALL")
    time.sleep(0.3)

    sampler.delete_all_samples()
    time.sleep(0.5)

    remaining = sampler.list_samples()
    assert len(remaining) == 0


def test_upload_multiple(sampler):
    """Upload 3 samples, verify count and names."""
    before = sampler.list_samples()

    freqs = [440.0, 880.0, 220.0]
    names = ["MULTI A", "MULTI B", "MULTI C"]
    for name, freq in zip(names, freqs):
        pcm = _short_pcm(0.05, freq=freq)
        sampler.upload_sample(pcm, 44100, name)
        time.sleep(0.3)

    after = sampler.list_samples()
    assert len(after) == len(before) + 3
    for name in names:
        assert name in after


# --- Tone row: 12 chromatic samples + program + playback ---

# 12-tone chromatic row from C3 to B3 (in semitone order)
CHROMATIC_NOTES = [
    ("A", 261.63),   # C3   MIDI 60
    ("B", 277.18),   # C#3  MIDI 61
    ("C", 293.66),   # D3   MIDI 62
    ("D", 311.13),   # D#3  MIDI 63
    ("E", 329.63),   # E3   MIDI 64
    ("F", 349.23),   # F3   MIDI 65
    ("G", 369.99),   # F#3  MIDI 66
    ("H", 392.00),   # G3   MIDI 67
    ("I", 415.30),   # G#3  MIDI 68
    ("J", 440.00),   # A3   MIDI 69
    ("K", 466.16),   # A#3  MIDI 70
    ("L", 493.88),   # B3   MIDI 71
]

# MIDI note numbers: C3=60 through B3=71
MIDI_BASE = 60


def test_tone_row_upload(sampler):
    """Upload 12 chromatic samples (A-L), verify all appear."""
    sampler.delete_all_samples()
    time.sleep(1.0)

    for i, (letter, freq) in enumerate(CHROMATIC_NOTES):
        pcm = _short_pcm(0.1, freq=freq)
        sampler.upload_sample(pcm, 44100, letter, original_pitch=MIDI_BASE + i)
        time.sleep(0.3)

    names = sampler.list_samples()
    print(f"\n12 samples uploaded: {names}")
    assert len(names) == 12
    for letter, _ in CHROMATIC_NOTES:
        assert letter in names


def test_probe_existing_program(sampler):
    """Read back existing program header to learn the actual format."""
    programs = sampler.list_programs()
    print(f"\nPrograms on device: {programs}")
    if not programs:
        pytest.skip("No programs on device to probe")

    # Read back program header at index 0
    prog_hdr = sampler.read_program_header(0)
    assert prog_hdr is not None, "RPDATA returned nothing"
    print(f"Program header size: {len(prog_hdr)} bytes")
    print(f"First 32 bytes: {prog_hdr[:32].hex(' ')}")
    print(f"Full hex dump ({len(prog_hdr)} bytes):")
    for i in range(0, len(prog_hdr), 16):
        chunk = prog_hdr[i:i + 16]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        print(f"  {i:04x}: {hex_str}")

    # Read back keygroup 0 -- also print raw payload info
    import logging
    logging.basicConfig(level=logging.INFO)
    kg_hdr = sampler.read_keygroup(0, 0)
    if kg_hdr is not None:
        print(f"\nKeygroup 0 header size: {len(kg_hdr)} bytes")
        print(f"First 32 bytes: {kg_hdr[:32].hex(' ')}")
        print(f"Full hex dump ({len(kg_hdr)} bytes):")
        for i in range(0, len(kg_hdr), 16):
            chunk = kg_hdr[i:i + 16]
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            print(f"  {i:04x}: {hex_str}")
    else:
        print("\nRKDATA returned nothing for keygroup 0")


def test_tone_row_program(sampler):
    """Create TONE_ROW program with 12 keygroups via S1000 PDATA/KDATA."""
    existing = sampler.list_programs()
    # Overwrite existing TONE ROW, or create at next available slot
    if "TONE ROW" in existing:
        slot = existing.index("TONE ROW")
    else:
        slot = len(existing)
    print(f"\nPrograms: {existing}, using slot {slot}")

    keygroups = []
    for i, (letter, _) in enumerate(CHROMATIC_NOTES):
        note = MIDI_BASE + i
        keygroups.append({
            "low_note": note,
            "high_note": note,
            "sample_name": letter,
        })

    sampler.create_program("TONE ROW", keygroups,
                           midi_channel=0, program_number=slot)
    time.sleep(1.0)

    programs = sampler.list_programs()
    print(f"Programs after create: {programs}")
    assert "TONE ROW" in programs, f"TONE ROW not in {programs}"

    # Verify keygroup 0 has correct data
    kg0 = sampler.read_keygroup(slot, 0)
    if kg0 is not None:
        from s2800.protocol import decode_akai_name
        lonote = kg0[3] if len(kg0) > 3 else -1
        hinote = kg0[4] if len(kg0) > 4 else -1
        sname = decode_akai_name(kg0[0x22:0x2E]) if len(kg0) > 0x2E else "?"
        print(f"Keygroup 0: LONOTE={lonote} HINOTE={hinote} SNAME1={sname}")
        assert lonote == 60, f"LONOTE should be 60 (C3), got {lonote}"
        assert sname == "A", f"SNAME1 should be 'A', got '{sname}'"
    else:
        print("Could not read keygroup 0 (may need S3000 codes)")


def test_play_major_scale(sampler):
    """Play C major scale over MIDI. Requires TONE_ROW program loaded."""
    # C major: C D E F G A B
    major_notes = [60, 62, 64, 65, 67, 69, 71]

    print("\nPlaying C major scale...")
    for note in major_notes:
        sampler.play_note(note, velocity=100, duration=0.3, channel=0)
        time.sleep(0.05)

    print("C major scale complete.")


def test_play_minor_scale(sampler):
    """Play C minor scale over MIDI. Requires TONE_ROW program loaded."""
    # C natural minor: C D Eb F G Ab Bb
    minor_notes = [60, 62, 63, 65, 67, 68, 70]

    print("\nPlaying C minor scale...")
    for note in minor_notes:
        sampler.play_note(note, velocity=100, duration=0.3, channel=0)
        time.sleep(0.05)

    print("C minor scale complete.")


def test_606_kit(sampler):
    """Upload 606 kit and create drum program with GM mapping."""
    import librosa
    import soundfile as sf

    # Delete all existing samples to start fresh
    print("\nClearing samples...")
    sampler.delete_all_samples()
    time.sleep(1.0)

    # 606 essentials (8 sounds to fit in S2800 RAM)
    drum_map = [
        ("606_01_kick.wav", 36, "KICK"),           # C1 (Bass Drum)
        ("606_03_snare.wav", 38, "SNARE"),         # D1 (Snare)
        ("606_05_ch.wav", 42, "CL HAT"),           # F#1 (Closed Hi-Hat)
        ("606_07_oh.wav", 46, "OP HAT"),           # A#1 (Open Hi-Hat)
        ("606_09_tom_lo.wav", 43, "TOM LO"),       # G1 (Low Tom)
        ("606_10_tom_hi.wav", 50, "TOM HI"),       # D2 (High Tom)
        ("606_11_cymbal.wav", 49, "CYMBAL"),       # C#2 (Crash)
        ("606_12_cymbal_accent.wav", 51, "CYM ACC"),   # D#2 (Ride)
    ]

    print(f"Uploading {len(drum_map)} 606 samples...")
    for filename, midi_note, name in drum_map:
        path = f"sounds/606/{filename}"
        # Load WAV and convert to mono 16-bit PCM
        audio, sr = librosa.load(path, sr=44100, mono=True)
        # Convert float32 [-1, 1] to int16 PCM
        pcm = (audio * 32767).astype(np.int16).tobytes()

        sampler.upload_sample(pcm, 44100, name, original_pitch=midi_note)
        print(f"  {name} @ note {midi_note}")
        time.sleep(0.3)

    samples = sampler.list_samples()
    print(f"Uploaded: {samples}")
    assert len(samples) == 8

    # Create 606 KIT program
    existing = sampler.list_programs()
    if "606 KIT" in existing:
        slot = existing.index("606 KIT")
    else:
        slot = len(existing)
    print(f"\nCreating 606 KIT program at slot {slot}...")

    keygroups = []
    for i, (_, midi_note, name) in enumerate(drum_map):
        keygroups.append({
            "low_note": midi_note,
            "high_note": midi_note,
            "sample_name": name,
        })

    sampler.create_program("606 KIT", keygroups, midi_channel=9, program_number=slot)
    time.sleep(1.0)

    programs = sampler.list_programs()
    print(f"Programs: {programs}")
    assert "606 KIT" in programs

    print("\n606 KIT created successfully!")
