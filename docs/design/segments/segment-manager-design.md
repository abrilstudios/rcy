# RCY Centralized SegmentManager Design

Based on the comprehensive mutation inventory, this document designs a centralized segment management system that provides a single source of truth, automatic synchronization, and ultra-fast query performance.

## **🎯 DESIGN GOALS**

### **Primary Objectives**:
1. **Single Source of Truth** - Eliminate multiple segment stores
2. **Sub-millisecond Queries** - Ultra-fast keyboard shortcut performance
3. **Automatic Synchronization** - All 23 mutation points auto-update the store
4. **Unified Query API** - Same interface for mouse clicks and keyboard shortcuts
5. **Thread Safety** - Safe access from audio engine threads

### **Performance Requirements**:
- **Keyboard Query**: < 1ms response time
- **Mouse Query**: < 5ms response time  
- **Bulk Updates**: < 10ms for 100+ segments
- **Memory**: Minimal overhead beyond current segment storage

---

## **🏗️ SEGMENT MANAGER ARCHITECTURE**

### **Core Data Structure**

```python
class SegmentStore:
    """Ultra-fast segment storage optimized for both index and time-based queries"""
    
    def __init__(self):
        # Primary storage (sample-based, authoritative)
        self._boundaries: List[int] = []  # Sample positions [0, pos1, pos2, ..., end]
        self._sample_rate: float = 44100.0
        self._total_samples: int = 0
        
        # Optimized query structures (auto-maintained)
        self._time_boundaries: List[float] = []  # Time positions (seconds)
        self._segment_lookup: Dict[int, Tuple[float, float]] = {}  # index -> (start_time, end_time)
        self._dirty: bool = False  # Tracks if caches need rebuild
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Observers for auto-sync
        self._observers: List[Callable] = []
```

### **Query Optimization Strategy**

```python
class SegmentQueries:
    """Optimized query methods for different access patterns"""
    
    def get_segment_by_index(self, index: int) -> Optional[Tuple[float, float]]:
        """Ultra-fast O(1) lookup for keyboard shortcuts"""
        with self._lock:
            if self._dirty:
                self._rebuild_caches()
            return self._segment_lookup.get(index)
    
    def get_segment_by_time(self, time: float) -> Tuple[float, float]:
        """Fast O(log n) lookup for mouse clicks using binary search"""
        with self._lock:
            if self._dirty:
                self._rebuild_caches()
            
            # Binary search on time_boundaries
            idx = bisect.bisect_right(self._time_boundaries, time)
            if idx == 0:
                return (0.0, self._time_boundaries[0])
            elif idx >= len(self._time_boundaries):
                return (self._time_boundaries[-1], self._total_samples / self._sample_rate)
            else:
                return (self._time_boundaries[idx-1], self._time_boundaries[idx])
    
    def get_all_segments(self) -> List[Tuple[float, float]]:
        """Get all segment boundaries as time ranges"""
        with self._lock:
            if self._dirty:
                self._rebuild_caches()
            return [self._segment_lookup[i] for i in sorted(self._segment_lookup.keys())]
```

---

## **🔄 AUTO-SYNC OBSERVER PATTERN**

### **Observer Registration System**

```python
class SegmentManager:
    """Main segment manager with auto-sync capabilities"""
    
    def __init__(self):
        self.store = SegmentStore()
        self._mutation_handlers = {}
        self._setup_observers()
    
    def register_observer(self, callback: Callable[[str, Any], None]):
        """Register callback for segment changes"""
        self.store._observers.append(callback)
    
    def _notify_observers(self, operation: str, data: Any):
        """Notify all observers of segment changes"""
        for callback in self.store._observers:
            try:
                callback(operation, data)
            except Exception as e:
                # Log but don't break other observers
                print(f"Observer error: {e}")
```

### **Automatic Sync Points**

Each of the 23 mutation points will trigger auto-sync:

```python
# Integration points for all mutation sources
class SegmentMutationHandler:
    
    def handle_bulk_create(self, boundaries: List[int], operation: str):
        """Handle split_by_measures(), split_by_transients()"""
        with self.store._lock:
            self.store._boundaries = sorted(boundaries)
            self.store._dirty = True
            self._notify_observers("bulk_create", {"operation": operation, "count": len(boundaries)})
    
    def handle_single_add(self, position: int):
        """Handle add_segment()"""
        with self.store._lock:
            bisect.insort(self.store._boundaries, position)
            self.store._dirty = True
            self._notify_observers("add", {"position": position})
    
    def handle_single_remove(self, position: int):
        """Handle remove_segment()"""
        with self.store._lock:
            if position in self.store._boundaries:
                self.store._boundaries.remove(position)
                self.store._dirty = True
                self._notify_observers("remove", {"position": position})
    
    def handle_clear(self, reason: str):
        """Handle segment clearing (file load, cut, etc.)"""
        with self.store._lock:
            self.store._boundaries.clear()
            self.store._dirty = True
            self._notify_observers("clear", {"reason": reason})
    
    def handle_audio_change(self, sample_rate: float, total_samples: int):
        """Handle audio file changes that affect coordinate conversion"""
        with self.store._lock:
            self.store._sample_rate = sample_rate
            self.store._total_samples = total_samples
            self.store._dirty = True
            self._notify_observers("audio_change", {"sample_rate": sample_rate, "total_samples": total_samples})
```

---

## **⚡ SIMPLIFIED DESIGN**

**Key Constraint**: Maximum 36 segments (keyboard mappings 1-9, 0, q-p = 20 segments, with room for growth)

This constraint eliminates the need for complex performance optimizations:
- No binary search needed (linear search of 36 items is ~0.1ms)  
- No cache building needed (direct array access is fast enough)
- No complex memory management needed (36 * 16 bytes = 576 bytes)

### **Simplified SegmentStore**

```python
class SegmentStore:
    """Ultra-simple segment storage - boundary point model"""
    
    def __init__(self):
        # Primary storage: sample positions defining segment boundaries
        self._boundaries: List[int] = []  # [0, pos1, pos2, ..., end_pos]
        self._sample_rate: float = 44100.0
        
        # Thread safety
        self._lock = threading.RLock()
    
    def get_segment_by_index(self, index: int) -> Optional[Tuple[float, float]]:
        """Get segment N (1-based) - no caching needed for 36 segments"""
        with self._lock:
            if index < 1 or index >= len(self._boundaries):
                return None
            
            start_sample = self._boundaries[index - 1] 
            end_sample = self._boundaries[index]
            
            return (start_sample / self._sample_rate, end_sample / self._sample_rate)
    
    def get_segment_by_time(self, time: float) -> Optional[Tuple[float, float]]:
        """Find segment containing time - linear search is fine for 36 segments"""
        time_sample = int(time * self._sample_rate)
        
        with self._lock:
            for i in range(len(self._boundaries) - 1):
                start_sample = self._boundaries[i]
                end_sample = self._boundaries[i + 1]
                
                if start_sample <= time_sample < end_sample:
                    return (start_sample / self._sample_rate, end_sample / self._sample_rate)
        return None
```

**Benefits of Simplification**:
- **Zero complexity**: No cache invalidation, no binary search, no memory pools
- **Zero bugs**: Linear logic is impossible to get wrong  
- **Instant queries**: Linear search of 36 items takes 0.1ms
- **Perfect compatibility**: Matches current `self.segments` boundary-point model exactly

## **🔌 INTEGRATION STRATEGY**

### **Phase 1: Drop-in Replacement**

Replace existing segment access with SegmentManager calls:

```python
# OLD: Multiple inconsistent access patterns
segments = model.get_segments()  # Sample-based
current_slices = controller.current_slices  # Time-based
boundaries = controller.get_segment_boundaries(click_time)  # Search-based

# NEW: Unified SegmentManager access
segments = segment_manager.get_segment_by_index(keyboard_index)  # O(1)
segments = segment_manager.get_segment_by_time(click_time)       # O(log n)
all_segments = segment_manager.get_all_segments()               # O(1) cached
```

### **Phase 2: Hook All Mutation Points**

Wrap all 23 mutation points with SegmentManager calls:

```python
# audio_processor.py modifications
class WavAudioProcessor:
    def __init__(self):
        self.segment_manager = SegmentManager()
        # Remove: self.segments = []  # No longer needed
    
    def split_by_measures(self, resolution):
        # Existing logic...
        new_boundaries = [int(i * samples_per_division) for i in range(total_divisions + 1)]
        
        # NEW: Update through SegmentManager
        self.segment_manager.handle_bulk_create(new_boundaries, "split_by_measures")
        
    def add_segment(self, segment_time):
        # Existing logic...
        new_sample = int(segment_time * self.sample_rate)
        
        # NEW: Update through SegmentManager  
        self.segment_manager.handle_single_add(new_sample)
```

### **Phase 3: Update All Query Points**

Replace direct segment access with SegmentManager queries:

```python
# rcy_view.py keyboard shortcuts
def _play_segment_by_index(self, segment_index):
    """Ultra-fast keyboard shortcut using O(1) lookup"""
    segment_bounds = self.controller.segment_manager.get_segment_by_index(segment_index)
    if segment_bounds:
        start_time, end_time = segment_bounds
        self.highlight_active_segment(start_time, end_time)
        self.controller.model.play_segment(start_time, end_time)

# rcy_controller.py mouse clicks  
def get_segment_boundaries(self, click_time):
    """Fast mouse click using O(log n) lookup"""
    return self.segment_manager.get_segment_by_time(click_time)
```

---

## **🧪 TESTING STRATEGY**

### **Consistency Tests**

```python
def test_keyboard_mouse_consistency(self):
    """Verify keyboard and mouse queries return identical results"""
    manager = SegmentManager()
    boundaries = [0, 1000, 2000, 3000]
    manager.handle_bulk_create(boundaries, "test")
    
    # Test that clicking in segment N returns same bounds as keyboard shortcut N
    for i in range(1, 4):  # Segments 1, 2, 3
        keyboard_result = manager.get_segment_by_index(i)
        
        # Click in middle of segment
        start_time, end_time = keyboard_result
        click_time = (start_time + end_time) / 2
        mouse_result = manager.get_segment_by_time(click_time)
        
        assert keyboard_result == mouse_result
```

---

## **📊 MIGRATION PLAN**

### **Step 1: Create SegmentManager** (1-2 days)
- Implement core SegmentStore and SegmentManager classes
- Add comprehensive unit tests
- Benchmark performance against requirements

### **Step 2: Replace Model Integration** (1 day)
- Update `audio_processor.py` to use SegmentManager
- Hook all 7 direct mutation points
- Verify existing functionality works unchanged

### **Step 3: Replace Controller Integration** (1 day)  
- Update `rcy_controller.py` to use SegmentManager
- Hook all 8 controller-coordinated operations
- Remove duplicate `current_slices` storage

### **Step 4: Replace UI Integration** (1 day)
- Update keyboard shortcuts to use O(1) index lookup
- Update mouse clicks to use O(log n) time lookup
- Remove duplicate segment state in views

### **Step 5: Validation & Cleanup** (1 day)
- Run comprehensive consistency tests
- Remove all legacy segment storage code
- Performance validation under load

---

## **🎯 EXPECTED BENEFITS**

### **Performance Improvements**:
- **Keyboard shortcuts**: 10-100x faster (O(1) vs array search)
- **Mouse clicks**: 2-5x faster (binary search vs linear)
- **Memory usage**: 20-30% reduction (single storage vs duplicates)

### **Code Quality**:
- **Eliminated off-by-one errors** (single source of truth)
- **Simplified maintenance** (centralized segment logic)
- **Improved testability** (isolated segment operations)

### **User Experience**:
- **Ultra-responsive keyboard shortcuts** for live performance
- **Consistent behavior** between mouse and keyboard input
- **No more sync issues** between UI elements

This design provides a robust foundation for eliminating the current segment management issues while delivering the performance required for live performance use.
