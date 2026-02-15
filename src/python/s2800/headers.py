"""S3000-family header builders for the S2800.

Builds the exact binary headers the S2800 expects for samples, programs,
and keygroups. Returns raw bytes (not nibble-encoded); caller nibble-encodes
before transmission.

Field offsets based on the S2800/S3000 SysEx specification:
https://lakai.sourceforge.net/docs/s2800_sysex.html
"""

from s2800.protocol import encode_akai_name


def build_sample_header(name: str, sample_length: int,
                        sample_rate: int = 44100,
                        original_pitch: int = 60) -> bytes:
    """Build a 192-byte S1000/S3000 sample header.

    Key offsets:
        0x00: Header ID (3 = S3000/S2800)
        0x01: Bandwidth (1 = 20kHz/full)
        0x02: Original pitch (MIDI note, 60 = C3)
        0x03-0x0E: Sample name (12 bytes, Akai encoding)
        0x0F: Sample rate valid flag (0x80)
        0x10: Number of active loops (0)
        0x13: Playback type (0 = no loop)
        0x1A-0x1D: Data length in samples (4 bytes LE)
        0x1E-0x21: Play start (4 bytes LE, 0)
        0x22-0x25: Play end (4 bytes LE, length - 1)
        0x8A-0x8B: Sample rate in Hz (2 bytes LE)

    Args:
        name: Sample name (max 12 chars)
        sample_length: Number of samples (not bytes)
        sample_rate: Sample rate in Hz
        original_pitch: MIDI note number (24-127)

    Returns:
        Exactly 192 bytes of raw header data
    """
    header = bytearray(0xC0)  # 192 bytes

    header[0x00] = 3   # S3000 format
    header[0x01] = 1   # 20kHz bandwidth (full)
    header[0x02] = original_pitch & 0x7F

    # Name at offset 0x03 (12 bytes)
    header[0x03:0x0F] = encode_akai_name(name)

    header[0x0F] = 0x80  # Sample rate valid
    header[0x10] = 0     # No active loops
    header[0x11] = 0     # First active loop index
    header[0x13] = 0     # Playback type: no loop

    # Data length at 0x1A (4 bytes LE)
    header[0x1A] = sample_length & 0xFF
    header[0x1B] = (sample_length >> 8) & 0xFF
    header[0x1C] = (sample_length >> 16) & 0xFF
    header[0x1D] = (sample_length >> 24) & 0xFF

    # Play start at 0x1E (0)
    # (already zero from bytearray init)

    # Play end at 0x22 (sample_length - 1)
    play_end = max(0, sample_length - 1)
    header[0x22] = play_end & 0xFF
    header[0x23] = (play_end >> 8) & 0xFF
    header[0x24] = (play_end >> 16) & 0xFF
    header[0x25] = (play_end >> 24) & 0xFF

    # Sample rate at 0x8A (2 bytes LE)
    header[0x8A] = sample_rate & 0xFF
    header[0x8B] = (sample_rate >> 8) & 0xFF

    return bytes(header)


def build_program_header(name: str, num_keygroups: int = 1,
                         midi_channel: int = 0,
                         program_number: int = 0) -> bytes:
    """Build a 192-byte S3000/S2800 program header.

    Field offsets from the S2800 SysEx specification:
        0x00-0x02: KGRP1@ -- block address of first keygroup (internal, leave 0)
        0x03-0x0E: PRNAME -- program name (12 bytes, Akai encoding)
        0x0F: PRGNUM -- MIDI program number (0-128)
        0x10: PMCHAN -- MIDI channel (0-15, 0xFF=OMNI)
        0x11: POLYPH -- polyphony depth (0-31 = 1-32 voices)
        0x12: PRIORT -- voice priority (0=low, 1=norm, 2=high, 3=hold)
        0x13: PLAYLO -- lower play range (21-127)
        0x14: PLAYHI -- upper play range (21-127)
        0x16: OUTPUT -- output routing (S2800: 0-2)
        0x17: STEREO -- L/R output levels (0-99)
        0x18: PANPOS -- pan balance (-50 to +50)
        0x19: PRLOUD -- basic loudness (0-99)
        0x27: B_PTCH -- pitch bend up range (0-24)
        0x2A: GROUPS -- number of keygroups (READ-ONLY, device manages)

    Args:
        name: Program name (max 12 chars)
        num_keygroups: Hint for keygroup count (device may override)
        midi_channel: MIDI channel (0-15, 0xFF = OMNI)
        program_number: MIDI program change number (0-128)

    Returns:
        Exactly 192 bytes of raw program header data
    """
    header = bytearray(192)

    # KGRP1@ at 0x00-0x02: leave as 0 (internal block address)

    # Program name at offset 3 (12 bytes)
    header[0x03:0x0F] = encode_akai_name(name)

    # MIDI program number at offset 15
    header[0x0F] = program_number & 0x7F

    # MIDI channel at offset 16
    header[0x10] = midi_channel & 0xFF

    # Polyphony at offset 17 (31 = 32 voices for full polyphony)
    header[0x11] = 31

    # Priority at offset 18 (1 = normal)
    header[0x12] = 1

    # Play range at offsets 19-20
    header[0x13] = 21    # A1 (lowest)
    header[0x14] = 127   # G8 (highest)

    # Output at offset 22 (0 = output 1)
    header[0x16] = 0

    # Stereo level at offset 23
    header[0x17] = 99

    # Pan at offset 24 (0 = center, stored as unsigned: 50 = center)
    header[0x18] = 50

    # Program loudness at offset 25
    header[0x19] = 99

    # Pitch bend at offset 39
    header[0x27] = 2

    # GROUPS at offset 42 (read-only, but set as hint)
    header[0x2A] = min(num_keygroups, 99)

    # Voice assignment at offset 61 (0 = OLDEST for drum kits)
    header[0x3D] = 0

    return bytes(header)


def build_keygroup(low_note: int, high_note: int, sample_name: str,
                   tune_semitones: int = 0, tune_cents: int = 0) -> bytes:
    """Build a keygroup header for S3000/S2800.

    Field offsets from the S2800 SysEx specification:
        0x00: KGIDENT -- block identifier (always 2)
        0x01-0x02: NXTKG@ -- next keygroup block address (internal, leave 0)
        0x03: LONOTE -- lower key range (21-127)
        0x04: HINOTE -- upper key range (21-127)
        0x07: FILFRQ -- filter frequency (0-99)
        0x08: K_FREQ -- filter key follow (0-12)
        0x0C: ATTAK1 -- envelope 1 attack (0-99)
        0x0D: DECAY1 -- envelope 1 decay (0-99)
        0x0E: SUSTN1 -- envelope 1 sustain (0-99)
        0x0F: RELSE1 -- envelope 1 release (0-99)
        Velocity Zone 1:
        0x22-0x2D: SNAME1 -- sample name (12 bytes, Akai encoding)
        0x2E: LOVEL1 -- lower velocity (0-127)
        0x2F: HIVEL1 -- upper velocity (0-127)
        0x35: ZPLAY1 -- playback type (0=as sample)

    Args:
        low_note: Low MIDI note for this keygroup (21-127)
        high_note: High MIDI note for this keygroup (21-127)
        sample_name: Sample name to assign to zone 1
        tune_semitones: Semitone tuning offset
        tune_cents: Fine tuning in cents

    Returns:
        Keygroup header bytes (192 bytes per S3000 spec)
    """
    header = bytearray(192)

    # KGIDENT at offset 0 (always 2 for keygroup blocks)
    header[0x00] = 2

    # NXTKG@ at offsets 1-2: leave as 0 (internal, device manages)

    # Key range
    header[0x03] = low_note & 0x7F
    header[0x04] = high_note & 0x7F

    # Tuning offset at offsets 5-6 (KGTUNO, 2 bytes)
    # Format: cents * 100 + semitones, as signed 16-bit
    tune_val = tune_cents + (tune_semitones * 100)
    header[0x05] = tune_val & 0xFF
    header[0x06] = (tune_val >> 8) & 0xFF

    # Filter frequency at offset 7 (99 = fully open)
    header[0x07] = 99

    # Filter key follow at offset 8
    header[0x08] = 12

    # Envelope 1 (amplitude) -- simple preset
    header[0x0C] = 0    # Attack: instant
    header[0x0D] = 50   # Decay: moderate
    header[0x0E] = 99   # Sustain: full
    header[0x0F] = 30   # Release: moderate

    # Envelope 2 (filter) -- default values
    header[0x14] = 0    # Attack
    header[0x15] = 50   # Decay
    header[0x16] = 0    # Sustain
    header[0x17] = 30   # Release

    # Velocity Zone 1 (offset 34-57)
    # Sample name at offset 34 (0x22), 12 bytes
    header[0x22:0x2E] = encode_akai_name(sample_name)

    # Velocity limits
    header[0x2E] = 0     # LOVEL1: lowest velocity
    header[0x2F] = 127   # HIVEL1: highest velocity

    # Tuning offset for zone 1 at offsets 48-49 (0x30-0x31)
    header[0x30] = 0
    header[0x31] = 0

    # Loudness offset for zone 1 at offset 50 (0x32)
    header[0x32] = 0

    # Playback type at offset 53 (0x35)
    header[0x35] = 0     # ZPLAY1: as sample

    # Mute group at offset 160 (0xA0)
    # 0xFF = OFF (no mute group), 0-31 = mute group number
    # For drum kits, typically set to OFF so drums don't cut each other
    header[0xA0] = 0xFF

    # Zones 2-4: leave sample names empty (all zeros = no sample assigned)
    # The device will ignore empty zones.

    return bytes(header)
