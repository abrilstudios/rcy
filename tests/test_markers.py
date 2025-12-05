"""Tests for the marker focus and nudge system."""

import pytest
from tui.markers import MarkerKind, Marker, MarkerManager


class TestMarkerModel:
    """Tests for Marker and MarkerKind."""

    def test_marker_kind_values(self):
        """Test MarkerKind enum values."""
        assert MarkerKind.REGION_START.value == "L"
        assert MarkerKind.REGION_END.value == "R"
        assert MarkerKind.SEGMENT.value == "SEGMENT"

    def test_marker_creation(self):
        """Test Marker dataclass."""
        marker = Marker(id="L", kind=MarkerKind.REGION_START, position=0)
        assert marker.id == "L"
        assert marker.kind == MarkerKind.REGION_START
        assert marker.position == 0


class TestMarkerManagerInit:
    """Tests for MarkerManager initialization."""

    def test_init_with_audio(self):
        """Test initialization with audio context."""
        mgr = MarkerManager(total_samples=44100, sample_rate=44100)
        assert mgr.get_marker("L") is not None
        assert mgr.get_marker("R") is not None
        assert mgr.get_marker("L").position == 0
        assert mgr.get_marker("R").position == 44100

    def test_init_without_audio(self):
        """Test initialization without audio context."""
        mgr = MarkerManager()
        assert len(mgr.get_all_markers()) == 0

    def test_default_focus_is_L(self):
        """Test that default focus is on L marker."""
        mgr = MarkerManager(total_samples=44100)
        assert mgr.focused_marker_id == "L"


class TestFocusModel:
    """Tests for focus management."""

    @pytest.fixture
    def mgr(self):
        return MarkerManager(total_samples=44100, sample_rate=44100)

    def test_set_focus_valid(self, mgr):
        """Test setting focus to valid marker."""
        assert mgr.set_focus("R")
        assert mgr.focused_marker_id == "R"

    def test_set_focus_invalid(self, mgr):
        """Test setting focus to invalid marker."""
        assert not mgr.set_focus("nonexistent")
        assert mgr.focused_marker_id == "L"  # Unchanged

    def test_cycle_focus_forward(self, mgr):
        """Test cycling focus forward."""
        # Add a segment marker between L and R
        mgr.add_segment_marker(22050)

        # Focus should cycle: L -> seg -> R -> L
        assert mgr.focused_marker_id == "L"
        mgr.cycle_focus()
        assert mgr.focused_marker.kind == MarkerKind.SEGMENT
        mgr.cycle_focus()
        assert mgr.focused_marker_id == "R"
        mgr.cycle_focus()
        assert mgr.focused_marker_id == "L"

    def test_cycle_focus_backward(self, mgr):
        """Test cycling focus backward."""
        mgr.add_segment_marker(22050)

        # Start at L, go backwards: L -> R -> seg -> L
        assert mgr.focused_marker_id == "L"
        mgr.cycle_focus(reverse=True)
        assert mgr.focused_marker_id == "R"
        mgr.cycle_focus(reverse=True)
        assert mgr.focused_marker.kind == MarkerKind.SEGMENT


class TestNudge:
    """Tests for nudge operations."""

    @pytest.fixture
    def mgr(self):
        return MarkerManager(
            total_samples=44100,
            sample_rate=44100,
            nudge_samples=100,
            min_region_samples=100,
        )

    def test_nudge_L_right(self, mgr):
        """Test nudging L marker right."""
        mgr.set_focus("L")
        assert mgr.nudge_right()
        assert mgr.get_marker("L").position == 100

    def test_nudge_L_left_at_zero(self, mgr):
        """Test nudging L marker left at position 0."""
        mgr.set_focus("L")
        assert not mgr.nudge_left()  # Can't go below 0
        assert mgr.get_marker("L").position == 0

    def test_nudge_R_left(self, mgr):
        """Test nudging R marker left."""
        mgr.set_focus("R")
        assert mgr.nudge_left()
        assert mgr.get_marker("R").position == 44100 - 100

    def test_nudge_R_right_at_end(self, mgr):
        """Test nudging R marker right at end."""
        mgr.set_focus("R")
        assert not mgr.nudge_right()  # Can't go beyond total_samples
        assert mgr.get_marker("R").position == 44100

    def test_nudge_segment_bidirectional(self, mgr):
        """Test nudging segment marker both directions."""
        marker_id = mgr.add_segment_marker(22050)
        mgr.set_focus(marker_id)

        assert mgr.nudge_right()
        assert mgr.get_marker(marker_id).position == 22150

        assert mgr.nudge_left()
        assert mgr.get_marker(marker_id).position == 22050

    def test_nudge_no_focus(self, mgr):
        """Test nudge with no focus returns False."""
        mgr._focused_marker_id = None
        assert not mgr.nudge_left()
        assert not mgr.nudge_right()


class TestConstraints:
    """Tests for marker constraints."""

    @pytest.fixture
    def mgr(self):
        return MarkerManager(
            total_samples=44100,
            sample_rate=44100,
            nudge_samples=100,
            min_region_samples=1000,
        )

    def test_L_cannot_cross_R(self, mgr):
        """Test L marker cannot cross R marker."""
        mgr.set_focus("L")
        # Try to nudge L way past R
        for _ in range(500):
            mgr.nudge_right()

        l_pos = mgr.get_marker("L").position
        r_pos = mgr.get_marker("R").position
        assert l_pos < r_pos
        assert r_pos - l_pos >= 1000  # min_region_samples

    def test_R_cannot_cross_L(self, mgr):
        """Test R marker cannot cross L marker."""
        mgr.set_focus("R")
        # Try to nudge R way past L
        for _ in range(500):
            mgr.nudge_left()

        l_pos = mgr.get_marker("L").position
        r_pos = mgr.get_marker("R").position
        assert l_pos < r_pos
        assert r_pos - l_pos >= 1000

    def test_segment_stays_in_region(self, mgr):
        """Test segment marker stays within L/R region."""
        marker_id = mgr.add_segment_marker(22050)
        mgr.set_focus(marker_id)

        # Nudge segment left many times
        for _ in range(500):
            mgr.nudge_left()

        seg_pos = mgr.get_marker(marker_id).position
        l_pos = mgr.get_marker("L").position
        assert seg_pos >= l_pos

    def test_moving_L_pushes_segments(self, mgr):
        """Test moving L clamps segment markers that would be outside."""
        # Add segment near start
        marker_id = mgr.add_segment_marker(500)
        mgr.set_focus("L")

        # Nudge L past the segment
        for _ in range(10):
            mgr.nudge_right()

        l_pos = mgr.get_marker("L").position
        seg_pos = mgr.get_marker(marker_id).position
        assert seg_pos >= l_pos


class TestSegmentMarkerManagement:
    """Tests for segment marker add/remove."""

    @pytest.fixture
    def mgr(self):
        return MarkerManager(total_samples=44100, sample_rate=44100)

    def test_add_segment_marker(self, mgr):
        """Test adding a segment marker."""
        marker_id = mgr.add_segment_marker(22050)
        assert marker_id.startswith("seg_")
        marker = mgr.get_marker(marker_id)
        assert marker is not None
        assert marker.position == 22050
        assert marker.kind == MarkerKind.SEGMENT

    def test_remove_segment_marker(self, mgr):
        """Test removing a segment marker."""
        marker_id = mgr.add_segment_marker(22050)
        assert mgr.remove_segment_marker(marker_id)
        assert mgr.get_marker(marker_id) is None

    def test_cannot_remove_L_R(self, mgr):
        """Test that L and R markers cannot be removed."""
        assert not mgr.remove_segment_marker("L")
        assert not mgr.remove_segment_marker("R")
        assert mgr.get_marker("L") is not None
        assert mgr.get_marker("R") is not None

    def test_focus_moves_after_delete(self, mgr):
        """Test focus moves to nearest after delete."""
        mgr.add_segment_marker(11025)
        marker_id = mgr.add_segment_marker(22050)
        mgr.add_segment_marker(33075)

        mgr.set_focus(marker_id)
        mgr.remove_segment_marker(marker_id)

        # Focus should move to nearest (one of the other segments)
        assert mgr.focused_marker_id is not None
        assert mgr.focused_marker_id != marker_id


class TestBoundarySync:
    """Tests for syncing with segment manager boundaries."""

    @pytest.fixture
    def mgr(self):
        return MarkerManager(total_samples=44100, sample_rate=44100)

    def test_sync_from_boundaries(self, mgr):
        """Test syncing from boundary list."""
        boundaries = [0, 11025, 22050, 33075, 44100]
        mgr.sync_from_boundaries(boundaries)

        # Should have L, R, and 3 segment markers
        markers = mgr.get_all_markers()
        assert len(markers) == 5  # L, R, 3 segments

        segment_markers = mgr.get_segment_markers()
        assert len(segment_markers) == 3
        assert segment_markers[0].position == 11025
        assert segment_markers[1].position == 22050
        assert segment_markers[2].position == 33075

    def test_get_boundaries(self, mgr):
        """Test getting boundaries from markers."""
        mgr.add_segment_marker(11025)
        mgr.add_segment_marker(22050)

        boundaries = mgr.get_boundaries()
        assert boundaries == [0, 11025, 22050, 44100]


class TestDebounce:
    """Tests for debounced recomputation."""

    def test_nudge_schedules_recompute(self):
        """Test that nudging schedules a recompute."""
        mgr = MarkerManager(total_samples=44100, debounce_ms=50)
        mgr.set_focus("L")
        mgr.nudge_right()
        assert mgr.pending_recompute

    def test_debounce_callback(self):
        """Test that recompute callback is called after debounce."""
        called = []

        def callback():
            called.append(True)

        mgr = MarkerManager(total_samples=44100, debounce_ms=0)  # No delay
        mgr.set_recompute_callback(callback)
        mgr.set_focus("L")
        mgr.nudge_right()

        # Immediately check - should trigger with 0ms debounce
        mgr.maybe_recompute()
        assert len(called) == 1
