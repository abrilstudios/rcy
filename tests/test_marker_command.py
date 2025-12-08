"""
Tests for /marker command functionality (Issue #169).

Run with: PYTHONPATH=src/python pytest tests/test_marker_command.py -v
"""

import pytest
from tui.markers import MarkerManager, MarkerKind


class TestBarBeatToSamples:
    """Test bar_beat_to_samples conversion."""

    @pytest.fixture
    def manager(self):
        """Create a MarkerManager at 44100Hz."""
        return MarkerManager(total_samples=441000, sample_rate=44100)  # 10 seconds

    def test_bar_1_beat_1_is_start(self, manager):
        """Bar 1, beat 1 should be at region start."""
        pos = manager.bar_beat_to_samples(
            bar=1, beat=1, tempo_bpm=120, region_start_samples=0
        )
        assert pos == 0

    def test_bar_2_is_one_bar_later(self, manager):
        """Bar 2 at 120 BPM should be 2 seconds (4 beats) later."""
        # At 120 BPM, one beat = 0.5 seconds = 22050 samples
        # One bar (4 beats) = 2 seconds = 88200 samples
        pos = manager.bar_beat_to_samples(
            bar=2, beat=1, tempo_bpm=120, region_start_samples=0
        )
        assert pos == 88200

    def test_beat_2_is_one_beat_later(self, manager):
        """Beat 2 at 120 BPM should be 0.5 seconds later."""
        # At 120 BPM, one beat = 0.5 seconds = 22050 samples
        pos = manager.bar_beat_to_samples(
            bar=1, beat=2, tempo_bpm=120, region_start_samples=0
        )
        assert pos == 22050

    def test_bar_3_beat_2(self, manager):
        """Bar 3, beat 2 at 120 BPM."""
        # Bar 3 beat 2 = (2 bars * 4 beats) + 1 beat = 9 beats from start
        # 9 beats * 0.5 sec/beat * 44100 samples/sec = 198450 samples
        pos = manager.bar_beat_to_samples(
            bar=3, beat=2, tempo_bpm=120, region_start_samples=0
        )
        assert pos == 198450

    def test_region_offset_applied(self, manager):
        """Region start offset should be added to position."""
        # Bar 1 beat 1 at offset 10000
        pos = manager.bar_beat_to_samples(
            bar=1, beat=1, tempo_bpm=120, region_start_samples=10000
        )
        assert pos == 10000

        # Bar 2 beat 1 at offset 10000
        pos2 = manager.bar_beat_to_samples(
            bar=2, beat=1, tempo_bpm=120, region_start_samples=10000
        )
        assert pos2 == 10000 + 88200

    def test_different_tempo(self, manager):
        """Test with different tempo (140 BPM)."""
        # At 140 BPM, one beat = 60/140 seconds = 0.4286 seconds
        # One bar = 4 * 0.4286 = 1.714 seconds = 75600 samples (approximately)
        pos = manager.bar_beat_to_samples(
            bar=2, beat=1, tempo_bpm=140, region_start_samples=0
        )
        expected = int(4 * (60.0 / 140) * 44100)  # 4 beats
        assert pos == expected

    def test_zero_tempo_returns_start(self, manager):
        """Zero tempo should return region start."""
        pos = manager.bar_beat_to_samples(
            bar=5, beat=3, tempo_bpm=0, region_start_samples=1000
        )
        assert pos == 1000

    def test_fractional_beat(self, manager):
        """Fractional beat should work."""
        # Beat 1.5 = 0.5 beats from beat 1
        pos_1 = manager.bar_beat_to_samples(
            bar=1, beat=1, tempo_bpm=120, region_start_samples=0
        )
        pos_1_5 = manager.bar_beat_to_samples(
            bar=1, beat=1.5, tempo_bpm=120, region_start_samples=0
        )
        # 0.5 beats at 120 BPM = 0.25 seconds = 11025 samples
        assert pos_1_5 == pos_1 + 11025


class TestFindOrCreateMarker:
    """Test find_or_create_marker_at functionality."""

    @pytest.fixture
    def manager(self):
        """Create a MarkerManager with L at 0, R at 44100."""
        mgr = MarkerManager(total_samples=44100, sample_rate=44100)  # 1 second
        return mgr

    def test_creates_new_marker_when_none_exist(self, manager):
        """Should create new marker when no segments exist."""
        marker_id = manager.find_or_create_marker_at(position=22050, snap_samples=100)

        assert marker_id.startswith("seg_")
        marker = manager.get_marker(marker_id)
        assert marker is not None
        assert marker.position == 22050
        assert marker.kind == MarkerKind.SEGMENT

    def test_creates_new_marker_when_far_from_existing(self, manager):
        """Should create new marker when position is far from existing."""
        # Add existing marker at 10000
        manager.add_segment_marker(10000)

        # Create at 30000 (20000 samples away, beyond 100 snap)
        marker_id = manager.find_or_create_marker_at(position=30000, snap_samples=100)

        # Should be a new marker, not the existing one
        assert marker_id != "seg_01"
        assert manager.get_marker(marker_id).position == 30000

    def test_moves_existing_marker_when_close(self, manager):
        """Should move existing marker when position is within snap distance."""
        # Add existing marker at 10000
        existing_id = manager.add_segment_marker(10000)

        # Create at 10050 (50 samples away, within 100 snap)
        marker_id = manager.find_or_create_marker_at(position=10050, snap_samples=100)

        # Should be the same marker, moved
        assert marker_id == existing_id
        assert manager.get_marker(marker_id).position == 10050

    def test_clamps_to_region(self, manager):
        """Position should be clamped to L/R region."""
        # Try to place marker before L (which is at 0)
        marker_id = manager.find_or_create_marker_at(position=-1000, snap_samples=100)
        assert manager.get_marker(marker_id).position == 0

        # Try to place marker after R (which is at 44100)
        marker_id = manager.find_or_create_marker_at(position=50000, snap_samples=100)
        assert manager.get_marker(marker_id).position == 44100

    def test_snap_to_nearest_not_just_any(self, manager):
        """Should snap to nearest marker, not just any marker within range."""
        # Add markers at 10000 and 11000
        manager.add_segment_marker(10000)
        manager.add_segment_marker(11000)

        # Place at 10600 with snap=1000 - should snap to 11000 (nearer)
        marker_id = manager.find_or_create_marker_at(position=10600, snap_samples=1000)

        # Should have moved the marker at 11000
        marker = manager.get_marker(marker_id)
        assert marker.position == 10600


class TestMarkerManagerIntegration:
    """Integration tests for marker command workflow."""

    @pytest.fixture
    def manager(self):
        """Create a MarkerManager simulating a 4-bar loop at 120 BPM."""
        # 4 bars at 120 BPM = 8 seconds = 352800 samples
        mgr = MarkerManager(total_samples=352800, sample_rate=44100)
        return mgr

    def test_full_marker_workflow(self, manager):
        """Test complete workflow: place marker, focus it, delete it."""
        # Place marker at bar 2 beat 1
        pos = manager.bar_beat_to_samples(bar=2, beat=1, tempo_bpm=120)
        marker_id = manager.find_or_create_marker_at(pos, snap_samples=441)

        # Focus it
        manager.set_focus(marker_id)
        assert manager.focused_marker_id == marker_id

        # Delete it
        success, msg = manager.delete_focused_marker()
        assert success is True
        assert manager.get_marker(marker_id) is None

    def test_multiple_markers_at_beat_positions(self, manager):
        """Place markers at each beat of bar 1."""
        marker_ids = []
        for beat in [1, 2, 3, 4]:
            pos = manager.bar_beat_to_samples(bar=1, beat=beat, tempo_bpm=120)
            marker_id = manager.find_or_create_marker_at(pos, snap_samples=100)
            marker_ids.append(marker_id)

        # Should have 4 markers
        segments = manager.get_segment_markers()
        assert len(segments) == 4

        # Positions should be 0, 22050, 44100, 66150
        positions = sorted([m.position for m in segments])
        expected = [0, 22050, 44100, 66150]
        assert positions == expected
