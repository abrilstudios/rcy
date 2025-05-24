"""
Centralized segment management system for RCY.

Simple boundary-point model with observer pattern for automatic synchronization.
Max 36 segments, so no complex optimizations needed.
"""

import threading
from typing import List, Tuple, Optional, Callable
from abc import ABC, abstractmethod


class SegmentObserver(ABC):
    """Abstract base class for segment change observers."""
    
    @abstractmethod
    def on_segments_changed(self, operation: str, **kwargs) -> None:
        """Called when segments are modified.
        
        Args:
            operation: Type of change ('set', 'add', 'remove', 'clear')
            **kwargs: Additional context about the change
        """
        pass


class SegmentStore:
    """Simple segment storage using boundary-point model.
    
    Stores sample positions as boundaries: [0, pos1, pos2, ..., end]
    N boundaries define N-1 segments between consecutive pairs.
    """
    
    def __init__(self):
        self._boundaries: List[int] = []  # Sample positions
        self._sample_rate: float = 44100.0
        self._lock = threading.RLock()
    
    def set_boundaries(self, boundaries: List[int], sample_rate: float) -> None:
        """Replace all boundaries with new list."""
        with self._lock:
            if not boundaries:
                self._boundaries = []
                return
                
            # Validate and sort boundaries
            sorted_boundaries = sorted(set(boundaries))  # Remove duplicates and sort
            
            # Validate boundaries are non-negative
            for boundary in boundaries:  # Check original list before sorting
                if boundary < 0:
                    raise ValueError(f"Boundary cannot be negative: {boundary}")
            
            # Validate increasing after sorting (duplicates removed by set())
            for i in range(1, len(sorted_boundaries)):
                if sorted_boundaries[i] <= sorted_boundaries[i-1]:
                    raise ValueError(f"Boundaries must be strictly increasing")
            
            self._boundaries = sorted_boundaries
            self._sample_rate = sample_rate
    
    def get_boundaries(self) -> List[int]:
        """Get all boundary sample positions."""
        with self._lock:
            return self._boundaries.copy()
    
    def get_segment_count(self) -> int:
        """Get number of segments (boundaries - 1)."""
        with self._lock:
            return max(0, len(self._boundaries) - 1)
    
    def get_segment_by_index(self, index: int) -> Optional[Tuple[float, float]]:
        """Get segment N (1-based) as (start_time, end_time) in seconds."""
        with self._lock:
            if index < 1 or index > self.get_segment_count():
                return None
            
            start_sample = self._boundaries[index - 1] 
            end_sample = self._boundaries[index]
            
            return (start_sample / self._sample_rate, end_sample / self._sample_rate)
    
    def get_segment_by_time(self, time: float) -> Optional[Tuple[float, float]]:
        """Find segment containing time. Linear search is fine for max 36 segments."""
        time_sample = int(time * self._sample_rate)
        
        with self._lock:
            for i in range(len(self._boundaries) - 1):
                start_sample = self._boundaries[i]
                end_sample = self._boundaries[i + 1]
                
                if start_sample <= time_sample < end_sample:
                    return (start_sample / self._sample_rate, end_sample / self._sample_rate)
        return None
    
    def get_all_segments(self) -> List[Tuple[float, float]]:
        """Get all segments as list of (start_time, end_time) tuples."""
        with self._lock:
            segments = []
            for i in range(len(self._boundaries) - 1):
                start_time = self._boundaries[i] / self._sample_rate
                end_time = self._boundaries[i + 1] / self._sample_rate
                segments.append((start_time, end_time))
            return segments
    
    def add_boundary(self, sample_position: int) -> None:
        """Add a new boundary at the given sample position."""
        with self._lock:
            if sample_position not in self._boundaries:
                self._boundaries.append(sample_position)
                self._boundaries.sort()
    
    def remove_boundary(self, sample_position: int) -> bool:
        """Remove boundary at given position. Returns True if found and removed."""
        with self._lock:
            if sample_position in self._boundaries:
                self._boundaries.remove(sample_position)
                return True
            return False
    
    def clear_boundaries(self) -> None:
        """Remove all boundaries."""
        with self._lock:
            self._boundaries.clear()


class SegmentManager:
    """Centralized segment management with observer pattern."""
    
    def __init__(self):
        self._store = SegmentStore()
        self._observers: List[SegmentObserver] = []
        self._lock = threading.RLock()
    
    def add_observer(self, observer: SegmentObserver) -> None:
        """Register an observer for segment changes."""
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)
    
    def remove_observer(self, observer: SegmentObserver) -> None:
        """Unregister an observer."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
    
    def _notify_observers(self, operation: str, **kwargs) -> None:
        """Notify all observers of segment changes."""
        for observer in self._observers:
            try:
                observer.on_segments_changed(operation, **kwargs)
            except Exception as e:
                # Log error but don't let one observer break others
                print(f"Error notifying observer {observer}: {e}")
    
    # Public API methods that delegate to store and notify observers
    
    def set_boundaries(self, boundaries: List[int], sample_rate: float) -> None:
        """Replace all boundaries. Used for bulk operations like split_by_measures."""
        with self._lock:
            old_count = self._store.get_segment_count()
            self._store.set_boundaries(boundaries, sample_rate)
            new_count = self._store.get_segment_count()
            self._notify_observers('set', old_count=old_count, new_count=new_count, boundaries=boundaries)
    
    def get_boundaries(self) -> List[int]:
        """Get all boundary sample positions (compatible with current self.segments)."""
        return self._store.get_boundaries()
    
    def get_segment_count(self) -> int:
        """Get number of segments."""
        return self._store.get_segment_count()
    
    def get_segment_by_index(self, index: int) -> Optional[Tuple[float, float]]:
        """Get segment N (1-based) for keyboard shortcuts. Ultra-fast O(1) access."""
        return self._store.get_segment_by_index(index)
    
    def get_segment_by_time(self, time: float) -> Optional[Tuple[float, float]]:
        """Find segment containing time for mouse clicks. Fast linear search."""
        return self._store.get_segment_by_time(time)
    
    def get_all_segments(self) -> List[Tuple[float, float]]:
        """Get all segments as time ranges."""
        return self._store.get_all_segments()
    
    def add_boundary(self, sample_position: int) -> None:
        """Add a new boundary."""
        with self._lock:
            self._store.add_boundary(sample_position)
            self._notify_observers('add', position=sample_position)
    
    def remove_boundary(self, sample_position: int) -> bool:
        """Remove boundary. Returns True if found and removed."""
        with self._lock:
            removed = self._store.remove_boundary(sample_position)
            if removed:
                self._notify_observers('remove', position=sample_position)
            return removed
    
    def clear_boundaries(self) -> None:
        """Remove all boundaries."""
        with self._lock:
            old_count = self._store.get_segment_count()
            self._store.clear_boundaries()
            self._notify_observers('clear', old_count=old_count)
    
    # Convenience methods for time-based operations
    
    def add_segment_at_time(self, time: float, sample_rate: float) -> None:
        """Add segment boundary at time position."""
        sample_position = int(time * sample_rate)
        self.add_boundary(sample_position)
    
    def remove_segment_at_time(self, time: float, sample_rate: float) -> bool:
        """Remove boundary closest to time position."""
        sample_position = int(time * sample_rate)
        
        # Find closest boundary
        boundaries = self.get_boundaries()
        if not boundaries:
            return False
            
        closest_boundary = min(boundaries, key=lambda b: abs(b - sample_position))
        return self.remove_boundary(closest_boundary)


# Global instance for the application
_segment_manager = None

def get_segment_manager() -> SegmentManager:
    """Get the global segment manager instance."""
    global _segment_manager
    if _segment_manager is None:
        _segment_manager = SegmentManager()
    return _segment_manager