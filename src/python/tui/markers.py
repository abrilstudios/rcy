"""Marker model for waveform editing.

Provides a unified focus model for L/R region markers and segment boundaries.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class MarkerKind(Enum):
    """Types of markers in the waveform."""
    REGION_START = "L"  # Left region boundary
    REGION_END = "R"    # Right region boundary
    SEGMENT = "SEGMENT" # Segment/slice boundary


@dataclass
class Marker:
    """A marker in the waveform.

    Attributes:
        id: Unique identifier (e.g., "L", "R", "seg_03")
        kind: Type of marker
        position: Sample index position
    """
    id: str
    kind: MarkerKind
    position: int


@dataclass
class DebounceState:
    """State for debounced recomputation."""
    pending_recompute: bool = False
    last_nudge_time_ms: float = 0.0


class MarkerManager:
    """Manages markers with focus model and nudge support.

    Provides:
    - Focus model: exactly one marker focused at a time
    - Bidirectional nudging with constraints
    - Debounced recomputation
    """

    def __init__(
        self,
        total_samples: int = 0,
        sample_rate: int = 44100,
        nudge_samples: int = 100,
        debounce_ms: float = 50.0,
        min_region_samples: int = 100,
    ):
        """Initialize the marker manager.

        Args:
            total_samples: Total samples in the audio file
            sample_rate: Sample rate in Hz
            nudge_samples: Samples to move per nudge
            debounce_ms: Milliseconds to wait before recompute
            min_region_samples: Minimum distance between L and R
        """
        self._total_samples = total_samples
        self._sample_rate = sample_rate
        self._nudge_samples = nudge_samples
        self._debounce_ms = debounce_ms
        self._min_region_samples = min_region_samples

        # Markers dict keyed by ID
        self._markers: dict[str, Marker] = {}

        # Currently focused marker ID
        self._focused_marker_id: Optional[str] = None

        # Debounce state
        self._debounce = DebounceState()

        # Recompute callback (set by caller)
        self._recompute_callback: Optional[callable] = None

        # Initialize L/R markers if we have audio
        if total_samples > 0:
            self._init_region_markers()

    def _init_region_markers(self) -> None:
        """Initialize L and R region markers."""
        self._markers["L"] = Marker(
            id="L",
            kind=MarkerKind.REGION_START,
            position=0,
        )
        self._markers["R"] = Marker(
            id="R",
            kind=MarkerKind.REGION_END,
            position=self._total_samples,
        )
        # Default focus to L
        self._focused_marker_id = "L"

    def set_audio_context(self, total_samples: int, sample_rate: int) -> None:
        """Set audio context and reset markers."""
        self._total_samples = total_samples
        self._sample_rate = sample_rate
        self._markers.clear()
        self._init_region_markers()

    def set_recompute_callback(self, callback: callable) -> None:
        """Set callback for deferred recomputation."""
        self._recompute_callback = callback

    # --- Focus Model ---

    @property
    def focused_marker_id(self) -> Optional[str]:
        """Get the ID of the currently focused marker."""
        return self._focused_marker_id

    @property
    def focused_marker(self) -> Optional[Marker]:
        """Get the currently focused marker."""
        if self._focused_marker_id:
            return self._markers.get(self._focused_marker_id)
        return None

    def set_focus(self, marker_id: str) -> bool:
        """Set focus to a marker.

        Args:
            marker_id: ID of marker to focus

        Returns:
            True if focus was set, False if marker not found
        """
        if marker_id in self._markers:
            self._focused_marker_id = marker_id
            return True
        return False

    def cycle_focus(self, reverse: bool = False) -> Optional[str]:
        """Cycle focus to next/previous marker in position order.

        Args:
            reverse: If True, cycle backwards

        Returns:
            ID of newly focused marker, or None if no markers
        """
        if not self._markers:
            return None

        # Sort markers by position
        sorted_ids = sorted(
            self._markers.keys(),
            key=lambda mid: self._markers[mid].position,
        )

        if not self._focused_marker_id or self._focused_marker_id not in sorted_ids:
            # Focus first marker
            self._focused_marker_id = sorted_ids[0]
        else:
            # Find current index and move
            current_idx = sorted_ids.index(self._focused_marker_id)
            if reverse:
                new_idx = (current_idx - 1) % len(sorted_ids)
            else:
                new_idx = (current_idx + 1) % len(sorted_ids)
            self._focused_marker_id = sorted_ids[new_idx]

        return self._focused_marker_id

    # --- Marker Access ---

    def get_marker(self, marker_id: str) -> Optional[Marker]:
        """Get a marker by ID."""
        return self._markers.get(marker_id)

    def get_all_markers(self) -> list[Marker]:
        """Get all markers sorted by position."""
        return sorted(self._markers.values(), key=lambda m: m.position)

    def get_segment_markers(self) -> list[Marker]:
        """Get only segment markers (not L/R)."""
        return sorted(
            [m for m in self._markers.values() if m.kind == MarkerKind.SEGMENT],
            key=lambda m: m.position,
        )

    # --- Segment Marker Management ---

    def add_segment_marker(self, position: int) -> str:
        """Add a segment marker at position.

        Args:
            position: Sample position

        Returns:
            ID of the new marker
        """
        # Generate unique ID
        existing_ids = [m.id for m in self._markers.values() if m.kind == MarkerKind.SEGMENT]
        idx = 1
        while f"seg_{idx:02d}" in existing_ids:
            idx += 1
        marker_id = f"seg_{idx:02d}"

        # Clamp to region
        l_pos = self._markers["L"].position
        r_pos = self._markers["R"].position
        position = max(l_pos, min(position, r_pos))

        self._markers[marker_id] = Marker(
            id=marker_id,
            kind=MarkerKind.SEGMENT,
            position=position,
        )
        return marker_id

    def remove_segment_marker(self, marker_id: str) -> bool:
        """Remove a segment marker (cannot remove L/R).

        Args:
            marker_id: ID of marker to remove

        Returns:
            True if removed, False if not found or is L/R
        """
        marker = self._markers.get(marker_id)
        if not marker or marker.kind != MarkerKind.SEGMENT:
            return False

        del self._markers[marker_id]

        # Update focus if we deleted the focused marker
        if self._focused_marker_id == marker_id:
            self._focus_nearest_after_delete(marker.position)

        return True

    def _focus_nearest_after_delete(self, deleted_position: int) -> None:
        """Focus nearest marker after deletion."""
        if not self._markers:
            self._focused_marker_id = None
            return

        # Find nearest marker to deleted position
        nearest_id = None
        nearest_dist = float('inf')

        for m in self._markers.values():
            dist = abs(m.position - deleted_position)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_id = m.id

        self._focused_marker_id = nearest_id

    def sync_from_boundaries(self, boundaries: list[int]) -> None:
        """Sync segment markers from boundary list.

        Keeps L/R markers and creates segment markers for internal boundaries.

        Args:
            boundaries: List of sample positions (includes 0 and total_samples)
        """
        # Remove existing segment markers
        to_remove = [m.id for m in self._markers.values() if m.kind == MarkerKind.SEGMENT]
        for mid in to_remove:
            del self._markers[mid]

        # Add segment markers for internal boundaries
        for i, pos in enumerate(boundaries):
            if pos == 0 or pos == self._total_samples:
                continue  # Skip L/R positions
            marker_id = f"seg_{i:02d}"
            self._markers[marker_id] = Marker(
                id=marker_id,
                kind=MarkerKind.SEGMENT,
                position=pos,
            )

    def get_boundaries(self) -> list[int]:
        """Get all boundary positions (for segment manager compatibility)."""
        positions = [m.position for m in self._markers.values()]
        return sorted(set(positions))

    # --- Nudge Operations ---

    def nudge_focused_marker(self, delta_samples: int) -> bool:
        """Nudge the focused marker by delta samples.

        Args:
            delta_samples: Positive = right, negative = left

        Returns:
            True if marker was moved, False if no focused marker or couldn't move
        """
        marker = self.focused_marker
        if not marker:
            return False

        new_pos = marker.position + delta_samples
        new_pos = self._clamp_marker_position(marker, new_pos)

        if new_pos == marker.position:
            return False

        marker.position = new_pos
        self._apply_marker_constraints(marker)
        self._schedule_recompute()
        return True

    def nudge_left(self) -> bool:
        """Nudge focused marker left."""
        return self.nudge_focused_marker(-self._nudge_samples)

    def nudge_right(self) -> bool:
        """Nudge focused marker right."""
        return self.nudge_focused_marker(self._nudge_samples)

    def _clamp_marker_position(self, marker: Marker, new_pos: int) -> int:
        """Clamp marker position based on its type and constraints."""
        if marker.kind == MarkerKind.REGION_START:
            # L: 0 <= pos < R - min_region
            r_pos = self._markers["R"].position
            upper = r_pos - self._min_region_samples
            return max(0, min(new_pos, upper))

        elif marker.kind == MarkerKind.REGION_END:
            # R: L + min_region <= pos <= total_samples
            l_pos = self._markers["L"].position
            lower = l_pos + self._min_region_samples
            return max(lower, min(new_pos, self._total_samples))

        else:  # SEGMENT
            # Segment: L <= pos <= R
            l_pos = self._markers["L"].position
            r_pos = self._markers["R"].position
            return max(l_pos, min(new_pos, r_pos))

    def _apply_marker_constraints(self, moved_marker: Marker) -> None:
        """Apply constraints after moving a marker."""
        if moved_marker.kind == MarkerKind.REGION_START:
            # Clamp segment markers that are now left of L
            l_pos = moved_marker.position
            for m in self._markers.values():
                if m.kind == MarkerKind.SEGMENT and m.position < l_pos:
                    m.position = l_pos

        elif moved_marker.kind == MarkerKind.REGION_END:
            # Clamp segment markers that are now right of R
            r_pos = moved_marker.position
            for m in self._markers.values():
                if m.kind == MarkerKind.SEGMENT and m.position > r_pos:
                    m.position = r_pos

    # --- Debounced Recompute ---

    def _schedule_recompute(self) -> None:
        """Schedule a debounced recompute."""
        now_ms = time.monotonic() * 1000
        self._debounce.pending_recompute = True
        self._debounce.last_nudge_time_ms = now_ms

    def maybe_recompute(self) -> bool:
        """Check if debounce period has passed and trigger recompute.

        Returns:
            True if recompute was triggered
        """
        if not self._debounce.pending_recompute:
            return False

        now_ms = time.monotonic() * 1000
        elapsed = now_ms - self._debounce.last_nudge_time_ms

        if elapsed >= self._debounce_ms:
            self._debounce.pending_recompute = False
            if self._recompute_callback:
                self._recompute_callback()
            return True
        return False

    @property
    def pending_recompute(self) -> bool:
        """Check if a recompute is pending."""
        return self._debounce.pending_recompute
