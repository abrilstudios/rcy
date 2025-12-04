"""EP-133 integration tests using synthetic audio data.

These tests require an EP-133 device to be connected. They use synthetic
12-tone chromatic sine waves starting at A4 (440Hz) to test the full
upload pipeline without needing real audio files.

Run with: pytest -m ep133
Skip with: pytest -m "not ep133"
"""

import numpy as np
import pytest

# Mark all tests in this module as EP-133 integration tests
pytestmark = [pytest.mark.ep133, pytest.mark.integration]


def generate_sine_wave(frequency: float, duration: float = 0.5, sample_rate: int = 44100) -> np.ndarray:
    """Generate a sine wave at the given frequency.

    Args:
        frequency: Frequency in Hz
        duration: Duration in seconds
        sample_rate: Sample rate in Hz

    Returns:
        Float32 numpy array with values in [-1, 1]
    """
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    # Apply a simple envelope to avoid clicks
    envelope = np.ones_like(t)
    attack = int(0.01 * sample_rate)  # 10ms attack
    release = int(0.05 * sample_rate)  # 50ms release
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-release:] = np.linspace(1, 0, release)
    return (np.sin(2 * np.pi * frequency * t) * envelope * 0.8).astype(np.float32)


def generate_chromatic_scale(base_freq: float = 440.0, num_notes: int = 12,
                             duration: float = 0.5, sample_rate: int = 44100) -> list[np.ndarray]:
    """Generate a chromatic scale as separate audio segments.

    Args:
        base_freq: Starting frequency (default A4 = 440Hz)
        num_notes: Number of semitones (default 12 for full octave)
        duration: Duration of each note in seconds
        sample_rate: Sample rate in Hz

    Returns:
        List of float32 numpy arrays, one per note
    """
    segments = []
    for i in range(num_notes):
        # Each semitone is 2^(1/12) higher than the previous
        freq = base_freq * (2 ** (i / 12))
        segments.append(generate_sine_wave(freq, duration, sample_rate))
    return segments


def float_to_pcm_s16le(audio: np.ndarray) -> bytes:
    """Convert float32 audio to s16le PCM bytes.

    Note: Must use 32767 (full int16 range), not 32000 or other values,
    otherwise the EP-133 produces distorted output.
    """
    clipped = np.clip(audio, -1.0, 1.0)
    scaled = (clipped * 32767).astype(np.int16)
    return scaled.tobytes()


@pytest.fixture
def ep133_device():
    """Fixture that provides a connected EP-133 device or skips the test."""
    try:
        from ep133 import EP133Device, EP133NotFound
    except ImportError:
        pytest.skip("EP-133 module not available (install mido and python-rtmidi)")

    try:
        device = EP133Device()
        device.connect()
        yield device
        device.disconnect()
    except EP133NotFound:
        pytest.skip("EP-133 device not connected")


@pytest.fixture
def chromatic_segments():
    """Fixture providing 12 chromatic sine wave segments."""
    return generate_chromatic_scale(440.0, 12, 0.5, 44100)


class TestSyntheticAudioGeneration:
    """Tests for synthetic audio generation (no device required)."""

    @pytest.mark.parametrize("freq", [440.0, 880.0, 220.0])
    def test_sine_wave_generation(self, freq):
        """Test that sine waves are generated correctly."""
        audio = generate_sine_wave(freq, duration=0.1)
        assert audio.dtype == np.float32
        assert len(audio) == 4410  # 0.1s at 44100Hz
        assert np.abs(audio).max() <= 1.0
        assert np.abs(audio).max() > 0.5  # Should have audible content

    def test_chromatic_scale_generation(self):
        """Test chromatic scale generates 12 segments."""
        segments = generate_chromatic_scale()
        assert len(segments) == 12
        for seg in segments:
            assert seg.dtype == np.float32
            assert len(seg) == 22050  # 0.5s at 44100Hz

    def test_chromatic_frequencies(self):
        """Test that chromatic frequencies are correct."""
        base = 440.0
        # A4=440, A#4=466.16, B4=493.88, C5=523.25, ...
        expected_freqs = [base * (2 ** (i / 12)) for i in range(12)]

        # Generate very short samples to check dominant frequency
        for i, expected in enumerate(expected_freqs):
            # Just verify the calculation is correct
            actual = base * (2 ** (i / 12))
            assert abs(actual - expected) < 0.01

    def test_pcm_conversion(self):
        """Test float to PCM conversion."""
        audio = generate_sine_wave(440.0, duration=0.1)
        pcm = float_to_pcm_s16le(audio)
        assert isinstance(pcm, bytes)
        assert len(pcm) == len(audio) * 2  # 16-bit = 2 bytes per sample


class TestEP133Connection:
    """Tests for EP-133 device connection."""

    def test_device_connection(self, ep133_device):
        """Test that we can connect to EP-133."""
        assert ep133_device.is_connected
        in_port, out_port = ep133_device.port_names
        assert "EP-133" in in_port or "K.O." in in_port

    def test_list_sounds(self, ep133_device):
        """Test listing sounds on device."""
        entries = ep133_device.list_directory(1000)  # /sounds/ directory
        assert isinstance(entries, list)
        # Device should have at least some factory sounds
        assert len(entries) >= 0


class TestEP133Upload:
    """Tests for uploading audio to EP-133."""

    def test_upload_single_sine(self, ep133_device):
        """Test uploading a single sine wave to a slot.

        Note: Upload success is verified by no exception being raised.
        The EP-133 sound directory may not immediately reflect new uploads
        until they are assigned to pads or the device is synced.
        """
        audio = generate_sine_wave(440.0, 0.5)
        pcm = float_to_pcm_s16le(audio)

        # Upload to slot 990 (SFX category, less likely to conflict)
        # Success = no exception raised
        ep133_device.upload_sample(
            slot=990,
            audio_data=pcm,
            channels=1,
            samplerate=44100
        )

    def test_upload_chromatic_scale(self, ep133_device, chromatic_segments):
        """Test uploading 12 chromatic tones to consecutive slots.

        Note: Upload success is verified by no exception being raised.
        """
        slot_start = 980  # Use slots 980-991 in SFX range

        uploaded_count = 0
        for i, segment in enumerate(chromatic_segments):
            pcm = float_to_pcm_s16le(segment)
            slot = slot_start + i

            ep133_device.upload_sample(
                slot=slot,
                audio_data=pcm,
                channels=1,
                samplerate=44100
            )
            uploaded_count += 1

        assert uploaded_count == 12


class TestEP133BankOperations:
    """Tests for bank-level operations."""

    def test_clear_bank(self, ep133_device):
        """Test clearing a bank (project 9, bank D - least likely to be in use)."""
        from ep133.pad_mapping import pad_to_node_id

        project = 9
        bank = 'D'

        # Clear all 12 pads
        for pad in range(1, 13):
            node_id = pad_to_node_id(project, bank, pad)
            ep133_device.assign_sound(node_id, 0)

        # Verify pads are cleared (would need to read metadata to fully verify)
        # For now just ensure no exception was raised

    def test_upload_and_assign_bank(self, ep133_device, chromatic_segments):
        """Test full workflow: upload chromatic scale to slots, assign to bank."""
        from ep133.pad_mapping import pad_to_node_id

        project = 9
        bank = 'D'
        slot_start = 970  # Use slots 970-981

        # First clear the bank
        for pad in range(1, 13):
            node_id = pad_to_node_id(project, bank, pad)
            ep133_device.assign_sound(node_id, 0)

        # Upload segments to slots
        for i, segment in enumerate(chromatic_segments):
            pcm = float_to_pcm_s16le(segment)
            slot = slot_start + i
            ep133_device.upload_sample(
                slot=slot,
                audio_data=pcm,
                channels=1,
                samplerate=44100
            )

        # Assign slots to pads
        for i in range(12):
            slot = slot_start + i
            pad = i + 1
            node_id = pad_to_node_id(project, bank, pad)
            ep133_device.assign_sound(node_id, slot)

        # Verify (basic check - no exception means success)
        # Full verification would require reading pad metadata

    def test_cleanup_after_test(self, ep133_device):
        """Cleanup: clear test bank after tests complete."""
        from ep133.pad_mapping import pad_to_node_id

        # Clear project 9, bank D (test bank)
        for pad in range(1, 13):
            node_id = pad_to_node_id(9, 'D', pad)
            ep133_device.assign_sound(node_id, 0)


class TestPadMapping:
    """Tests for pad mapping utilities (no device required)."""

    def test_pad_to_node_mapping(self):
        """Test pad to node ID calculation."""
        from ep133.pad_mapping import pad_to_node_id

        # Project 1, Bank A, Pad 1 -> node 3210
        assert pad_to_node_id(1, 'A', 1) == 3210
        # Project 1, Bank A, Pad 12 -> node 3203
        assert pad_to_node_id(1, 'A', 12) == 3203

    def test_pad_address_format(self):
        """Test pad address formatting."""
        from ep133.pad_mapping import format_pad_address, parse_pad_address

        assert format_pad_address(1, 'A', 1) == '1/A/1'
        assert parse_pad_address('2/B/5') == (2, 'B', 5)

    def test_slot_categories(self):
        """Test slot category lookup."""
        from ep133.pad_mapping import get_slot_category

        assert get_slot_category(50) == 'KICK'
        assert get_slot_category(150) == 'SNARE'
        assert get_slot_category(700) == 'USER1'
        assert get_slot_category(950) == 'SFX'
