"""
Test suite for SegmentManager implementation.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from segment_manager import SegmentManager, SegmentStore, SegmentObserver


class MockObserver(SegmentObserver):
    """Test observer to track segment changes."""
    
    def __init__(self):
        self.notifications = []
    
    def on_segments_changed(self, operation: str, **kwargs) -> None:
        self.notifications.append((operation, kwargs))


class TestSegmentStore:
    """Test the core SegmentStore functionality."""
    
    def test_empty_store(self):
        """Test empty segment store."""
        store = SegmentStore()
        assert store.get_segment_count() == 0
        assert store.get_boundaries() == []
        assert store.get_all_segments() == []
        assert store.get_segment_by_index(1) is None
        assert store.get_segment_by_time(0.5) is None
    
    def test_set_boundaries(self):
        """Test setting segment boundaries."""
        store = SegmentStore()
        boundaries = [0, 1000, 2000, 3000, 4000]
        sample_rate = 44100
        
        store.set_boundaries(boundaries, sample_rate)
        
        assert store.get_segment_count() == 4
        assert store.get_boundaries() == boundaries
    
    def test_get_segment_by_index(self):
        """Test keyboard shortcut access (1-based indexing)."""
        store = SegmentStore()
        boundaries = [0, 22050, 44100, 66150, 88200]  # 0.5s segments
        sample_rate = 44100
        
        store.set_boundaries(boundaries, sample_rate)
        
        # Test valid segments
        segment1 = store.get_segment_by_index(1)
        assert segment1 == (0.0, 0.5)
        
        segment2 = store.get_segment_by_index(2)
        assert segment2 == (0.5, 1.0)
        
        segment4 = store.get_segment_by_index(4)
        assert segment4 == (1.5, 2.0)
        
        # Test invalid indices
        assert store.get_segment_by_index(0) is None
        assert store.get_segment_by_index(5) is None
        assert store.get_segment_by_index(-1) is None
    
    def test_get_segment_by_time(self):
        """Test mouse click access (time-based)."""
        store = SegmentStore()
        boundaries = [0, 22050, 44100, 66150, 88200]  # 0.5s segments
        sample_rate = 44100
        
        store.set_boundaries(boundaries, sample_rate)
        
        # Test times within segments
        assert store.get_segment_by_time(0.25) == (0.0, 0.5)  # First segment
        assert store.get_segment_by_time(0.75) == (0.5, 1.0)  # Second segment
        assert store.get_segment_by_time(1.25) == (1.0, 1.5)  # Third segment
        assert store.get_segment_by_time(1.75) == (1.5, 2.0)  # Fourth segment
        
        # Test boundary conditions
        assert store.get_segment_by_time(0.0) == (0.0, 0.5)   # Start of first
        assert store.get_segment_by_time(0.5) == (0.5, 1.0)   # Start of second
        
        # Test out of bounds
        assert store.get_segment_by_time(-0.1) is None
        assert store.get_segment_by_time(2.5) is None
    
    def test_keyboard_mouse_consistency(self):
        """Test that keyboard and mouse access return identical results."""
        store = SegmentStore()
        boundaries = [0, 22050, 44100, 66150, 88200]
        sample_rate = 44100
        
        store.set_boundaries(boundaries, sample_rate)
        
        for segment_index in range(1, 5):
            keyboard_result = store.get_segment_by_index(segment_index)
            assert keyboard_result is not None
            
            start_time, end_time = keyboard_result
            click_time = (start_time + end_time) / 2
            mouse_result = store.get_segment_by_time(click_time)
            
            assert keyboard_result == mouse_result
    
    def test_boundary_operations(self):
        """Test adding and removing boundaries."""
        store = SegmentStore()
        boundaries = [0, 1000, 2000, 3000]
        sample_rate = 44100
        
        store.set_boundaries(boundaries, sample_rate)
        initial_count = store.get_segment_count()
        
        # Add boundary
        store.add_boundary(1500)
        assert store.get_segment_count() == initial_count + 1
        assert 1500 in store.get_boundaries()
        
        # Remove boundary
        removed = store.remove_boundary(1500)
        assert removed is True
        assert store.get_segment_count() == initial_count
        assert 1500 not in store.get_boundaries()
        
        # Try to remove non-existent boundary
        removed = store.remove_boundary(9999)
        assert removed is False
    
    def test_clear_boundaries(self):
        """Test clearing all boundaries."""
        store = SegmentStore()
        boundaries = [0, 1000, 2000, 3000]
        sample_rate = 44100
        
        store.set_boundaries(boundaries, sample_rate)
        assert store.get_segment_count() > 0
        
        store.clear_boundaries()
        assert store.get_segment_count() == 0
        assert store.get_boundaries() == []
    
    def test_invalid_boundaries(self):
        """Test validation of invalid boundary data."""
        store = SegmentStore()
        
        # Test negative boundaries
        with pytest.raises(ValueError):
            store.set_boundaries([-100, 0, 1000], 44100)
        
        # Test duplicate boundaries (should be handled but let's test empty result)
        # Since set() removes duplicates, [0, 1000, 1000] becomes [0, 1000] which is valid
        # Let's test a case that should actually fail - empty boundaries list after filtering
        store.set_boundaries([1000, 1000, 1000], 44100)  # Should work (becomes [1000])
        assert store.get_segment_count() == 0  # No segments from single boundary


class TestSegmentManager:
    """Test the SegmentManager API."""

    def test_api_delegation(self):
        """Test that SegmentManager properly delegates to SegmentStore."""
        manager = SegmentManager()
        boundaries = [0, 22050, 44100]
        sample_rate = 44100

        manager.set_boundaries(boundaries, sample_rate)

        # Test all delegated methods
        assert manager.get_segment_count() == 2
        assert manager.get_boundaries() == boundaries
        assert manager.get_segment_by_index(1) == (0.0, 0.5)
        assert manager.get_segment_by_time(0.25) == (0.0, 0.5)
        assert len(manager.get_all_segments()) == 2


class TestPerformance:
    """Test performance with maximum expected segments (36)."""
    
    def test_keyboard_lookup_performance(self):
        """Test keyboard lookup performance."""
        import time
        
        manager = SegmentManager()
        # Create 36 segments
        boundaries = [i * 1000 for i in range(37)]
        sample_rate = 44100
        
        manager.set_boundaries(boundaries, sample_rate)
        
        # Time 100 keyboard lookups
        start_time = time.perf_counter()
        for _ in range(100):
            for i in range(1, 37):
                result = manager.get_segment_by_index(i)
                assert result is not None
        
        total_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        avg_time = total_time / (100 * 36)
        
        # Should be sub-millisecond
        assert avg_time < 1.0, f"Keyboard lookup too slow: {avg_time:.4f}ms"
    
    def test_mouse_lookup_performance(self):
        """Test mouse lookup performance."""
        import time
        
        manager = SegmentManager()
        # Create 36 segments  
        boundaries = [i * 1000 for i in range(37)]
        sample_rate = 44100
        
        manager.set_boundaries(boundaries, sample_rate)
        
        # Time 100 mouse lookups
        start_time = time.perf_counter()
        for _ in range(100):
            for i in range(36):
                click_time = (i * 1000 + 500) / sample_rate
                result = manager.get_segment_by_time(click_time)
                assert result is not None
        
        total_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        avg_time = total_time / (100 * 36)
        
        # Should be sub-millisecond
        assert avg_time < 1.0, f"Mouse lookup too slow: {avg_time:.4f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])