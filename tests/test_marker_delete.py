"""
Tests for marker deletion functionality (Issue #168).

Run with: PYTHONPATH=src/python pytest tests/test_marker_delete.py -v
"""

import pytest
from tui.markers import MarkerManager, MarkerKind


class TestMarkerDelete:
    """Test delete_focused_marker functionality."""

    @pytest.fixture
    def manager(self):
        """Create a MarkerManager with some segment markers."""
        mgr = MarkerManager(total_samples=44100, sample_rate=44100)
        # Add some segment markers
        mgr.add_segment_marker(11025)  # 0.25s
        mgr.add_segment_marker(22050)  # 0.5s
        mgr.add_segment_marker(33075)  # 0.75s
        return mgr

    def test_delete_segment_marker(self, manager):
        """Deleting a segment marker should succeed."""
        # Focus a segment marker
        manager.set_focus("seg_01")
        assert manager.focused_marker.kind == MarkerKind.SEGMENT

        success, message = manager.delete_focused_marker()

        assert success is True
        assert message == "seg_01"
        assert manager.get_marker("seg_01") is None

    def test_cannot_delete_L_marker(self, manager):
        """Deleting L marker should fail."""
        manager.set_focus("L")
        assert manager.focused_marker.kind == MarkerKind.REGION_START

        success, message = manager.delete_focused_marker()

        assert success is False
        assert "Cannot delete L/R" in message
        assert manager.get_marker("L") is not None

    def test_cannot_delete_R_marker(self, manager):
        """Deleting R marker should fail."""
        manager.set_focus("R")
        assert manager.focused_marker.kind == MarkerKind.REGION_END

        success, message = manager.delete_focused_marker()

        assert success is False
        assert "Cannot delete L/R" in message
        assert manager.get_marker("R") is not None

    def test_focus_moves_after_delete(self, manager):
        """After deleting, focus should move to nearest marker."""
        # Focus middle marker
        manager.set_focus("seg_02")
        deleted_pos = manager.focused_marker.position

        success, _ = manager.delete_focused_marker()

        assert success is True
        # Focus should have moved to a nearby marker
        assert manager.focused_marker_id is not None
        assert manager.focused_marker_id != "seg_02"

    def test_delete_with_no_focus(self, manager):
        """Deleting with no focus should fail gracefully."""
        manager._focused_marker_id = None

        success, message = manager.delete_focused_marker()

        assert success is False
        assert "No marker focused" in message

    def test_delete_all_segments_focuses_L_or_R(self, manager):
        """Deleting all segments should leave focus on L or R."""
        # Delete all segment markers
        for marker_id in ["seg_01", "seg_02", "seg_03"]:
            manager.set_focus(marker_id)
            manager.delete_focused_marker()

        # Should only have L and R left
        all_markers = manager.get_all_markers()
        assert len(all_markers) == 2
        assert all(m.kind != MarkerKind.SEGMENT for m in all_markers)

        # Focus should be on L or R
        assert manager.focused_marker_id in ("L", "R")

    def test_boundaries_update_after_delete(self, manager):
        """get_boundaries should reflect deletion."""
        initial_boundaries = manager.get_boundaries()
        initial_count = len(initial_boundaries)

        manager.set_focus("seg_01")
        manager.delete_focused_marker()

        new_boundaries = manager.get_boundaries()
        assert len(new_boundaries) == initial_count - 1

    def test_segment_markers_list_after_delete(self, manager):
        """get_segment_markers should not include deleted marker."""
        initial_segments = manager.get_segment_markers()
        assert len(initial_segments) == 3

        manager.set_focus("seg_02")
        manager.delete_focused_marker()

        remaining_segments = manager.get_segment_markers()
        assert len(remaining_segments) == 2
        assert all(m.id != "seg_02" for m in remaining_segments)
