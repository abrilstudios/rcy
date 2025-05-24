"""
Redesigned SegmentManager based on specification:
- Always maintains start (0) and end (total_samples) boundaries
- Segment-focused API instead of boundary-focused
- Enforces invariant: N boundaries = N-1 segments
"""

import threading
from typing import List, Tuple, Optional, Callable
from abc import ABC, abstractmethod


class SegmentObserver(ABC):
    """Abstract base class for segment change observers."""
    
    @abstractmethod
    def on_segments_changed(self, operation: str, **kwargs) -> None:
        """Called when segments are modified."""
        pass


class SegmentStore:
    """Segment storage that always maintains file coverage."""
    
    def __init__(self, total_samples: int = 0, sample_rate: float = 44100.0):
        """Initialize with audio file context."""
        self._total_samples = total_samples
        self._sample_rate = sample_rate
        # INVARIANT: Always start with boundaries [0, total_samples] (1 segment)
        self._boundaries: List[int] = [0, total_samples] if total_samples > 0 else []
        self._lock = threading.RLock()
    
    def set_audio_context(self, total_samples: int, sample_rate: float) -> None:
        """Set audio file context and initialize default single segment."""
        with self._lock:
            self._total_samples = total_samples
            self._sample_rate = sample_rate
            # Initialize with single segment covering entire file
            self._boundaries = [0, total_samples]
    
    def set_internal_boundaries(self, internal_positions: List[int]) -> None:
        """Set internal boundaries (automatically adds start/end boundaries)."""
        with self._lock:
            if self._total_samples == 0:
                raise RuntimeError("Must call set_audio_context() first")
            
            # Validate internal positions
            for pos in internal_positions:
                if pos < 0 or pos > self._total_samples:
                    raise ValueError(f"Boundary {pos} outside valid range [0, {self._total_samples}]")
            
            # Remove duplicates and sort
            unique_positions = sorted(set(internal_positions))
            
            # ENFORCE INVARIANT: Always include start and end
            self._boundaries = [0]
            for pos in unique_positions:
                if pos != 0 and pos != self._total_samples:  # Skip start/end if provided
                    self._boundaries.append(pos)
            self._boundaries.append(self._total_samples)
    
    def add_boundary(self, position: int) -> None:
        """Add a boundary at position (maintains start/end invariant)."""
        with self._lock:
            if position <= 0 or position >= self._total_samples:
                return  # Cannot add boundary at start/end (always maintained)
            
            if position not in self._boundaries:
                self._boundaries.append(position)
                self._boundaries.sort()
    
    def remove_boundary(self, position: int) -> bool:
        """Remove boundary at position (cannot remove start/end)."""
        with self._lock:
            if position == 0 or position == self._total_samples:
                return False  # Cannot remove start/end boundaries
            
            if position in self._boundaries:
                self._boundaries.remove(position)
                return True
            return False
    
    def get_boundaries(self) -> List[int]:
        """Get all boundaries (always includes start/end)."""
        with self._lock:
            return self._boundaries.copy()
    
    def get_segment_count(self) -> int:
        """Get number of segments."""
        with self._lock:
            return max(0, len(self._boundaries) - 1)
    
    def get_segment_by_index(self, index: int) -> Optional[Tuple[float, float]]:
        """Get segment N (1-based) as (start_time, end_time)."""
        with self._lock:
            if index < 1 or index > self.get_segment_count():
                return None
            
            start_sample = self._boundaries[index - 1]
            end_sample = self._boundaries[index]
            
            return (start_sample / self._sample_rate, end_sample / self._sample_rate)
    
    def get_segment_by_time(self, time: float) -> Optional[Tuple[float, float]]:
        """Find segment containing time."""
        time_sample = int(time * self._sample_rate)
        
        with self._lock:
            for i in range(len(self._boundaries) - 1):
                start_sample = self._boundaries[i]
                end_sample = self._boundaries[i + 1]
                
                if start_sample <= time_sample < end_sample:
                    return (start_sample / self._sample_rate, end_sample / self._sample_rate)
        return None
    
    def get_all_segments(self) -> List[Tuple[float, float]]:
        """Get all segments as (start_time, end_time) pairs."""
        with self._lock:
            segments = []
            for i in range(len(self._boundaries) - 1):
                start_time = self._boundaries[i] / self._sample_rate
                end_time = self._boundaries[i + 1] / self._sample_rate
                segments.append((start_time, end_time))
            return segments
    
    def clear_to_single_segment(self) -> None:
        """Reset to single segment covering entire file."""
        with self._lock:
            self._boundaries = [0, self._total_samples]


class SegmentManager:
    """Simplified segment management with guaranteed invariants."""
    
    def __init__(self):
        self._store = SegmentStore()
        self._observers: List[SegmentObserver] = []
        self._lock = threading.RLock()
    
    def set_audio_context(self, total_samples: int, sample_rate: float) -> None:
        """Initialize with audio file - creates single segment covering entire file."""
        with self._lock:
            self._store.set_audio_context(total_samples, sample_rate)
            self._notify_observers('audio_loaded', total_samples=total_samples, sample_rate=sample_rate)
    
    def split_by_positions(self, positions: List[int]) -> None:
        """Split audio at given positions (used by split_by_measures, split_by_transients)."""
        with self._lock:
            self._store.set_internal_boundaries(positions)
            self._notify_observers('split', position_count=len(positions))
    
    def add_segment_boundary(self, time: float) -> None:
        """Add segment boundary at time position."""
        with self._lock:
            sample_rate = self._store._sample_rate
            position = int(time * sample_rate)
            self._store.add_boundary(position)
            self._notify_observers('add', time=time)
    
    def remove_segment_boundary(self, time: float) -> bool:
        """Remove boundary closest to time position."""
        with self._lock:
            sample_rate = self._store._sample_rate
            position = int(time * sample_rate)
            removed = self._store.remove_boundary(position)
            if removed:
                self._notify_observers('remove', time=time)
            return removed
    
    def clear_segments(self) -> None:
        """Reset to single segment covering entire file."""
        with self._lock:
            self._store.clear_to_single_segment()
            self._notify_observers('clear')
    
    # Query methods (delegate to store)
    def get_segment_count(self) -> int:
        return self._store.get_segment_count()
    
    def get_segment_by_index(self, index: int) -> Optional[Tuple[float, float]]:
        return self._store.get_segment_by_index(index)
    
    def get_segment_by_time(self, time: float) -> Optional[Tuple[float, float]]:
        return self._store.get_segment_by_time(time)
    
    def get_all_segments(self) -> List[Tuple[float, float]]:
        return self._store.get_all_segments()
    
    def get_boundaries(self) -> List[int]:
        """Get boundary positions (for backward compatibility)."""
        return self._store.get_boundaries()
    
    # Observer management
    def add_observer(self, observer: SegmentObserver) -> None:
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)
    
    def remove_observer(self, observer: SegmentObserver) -> None:
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
    
    def _notify_observers(self, operation: str, **kwargs) -> None:
        for observer in self._observers:
            try:
                observer.on_segments_changed(operation, **kwargs)
            except Exception as e:
                print(f"Error notifying observer {observer}: {e}")


# Global instance for the application
_segment_manager = None

def get_segment_manager() -> SegmentManager:
    """Get the global segment manager instance."""
    global _segment_manager
    if _segment_manager is None:
        _segment_manager = SegmentManager()
    return _segment_manager