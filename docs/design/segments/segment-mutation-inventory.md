# RCY Segment Mutation Points - Complete Inventory

This document identifies every location in the RCY codebase where segments can be created, modified, or deleted. This analysis forms the foundation for designing a centralized segment management system.

## **SEGMENT MUTATION POINTS - COMPLETE INVENTORY**

### **🔧 DIRECT SEGMENT OPERATIONS** (7 operations)

**File**: `audio_processor.py` - Core segment storage: `self.segments[]`

1. **CLEAR** `self.segments = []`
   - **Triggers**: Object init, file load, audio cutting
   - **Locations**: Lines 25, 119, 517, 802

2. **CREATE BULK** `split_by_measures()` (Lines 203-231)
   - **Trigger**: User clicks "Split by Measures" 
   - **Logic**: Equal time divisions based on musical measures

3. **CREATE BULK** `split_by_transients()` (Lines 233-265)
   - **Trigger**: User clicks "Split by Transients" or changes threshold
   - **Logic**: AI-based onset detection using librosa

4. **CREATE SINGLE** `add_segment()` (Lines 280-288)
   - **Trigger**: Alt+Click on waveform
   - **Logic**: Insert new segment, sort array

5. **DELETE SINGLE** `remove_segment()` (Lines 267-278)
   - **Trigger**: Ctrl+Alt+Click on waveform
   - **Logic**: Remove closest segment to click position

### **🎛️ CONTROLLER COORDINATED OPERATIONS** (8 operations)

**File**: `rcy_controller.py` - Orchestrates changes via model

6. **CLEAR** `load_audio_file()` (Lines 135-230)
   - **Trigger**: User imports new audio file

7. **CLEAR** `load_preset()` (Lines 232-281)
   - **Trigger**: User selects preset from menu

8. **CREATE BULK** `split_audio()` (Lines 503-512)
   - **Trigger**: UI split buttons → delegates to model

9. **CREATE SINGLE** `add_segment()` (Lines 523-525)
   - **Trigger**: UI signals → delegates to model

10. **DELETE SINGLE** `remove_segment()` (Lines 514-521)
    - **Trigger**: UI signals → delegates to model

11. **CLEAR** `cut_audio()` (Lines 756-847, 802)
    - **Trigger**: User cuts audio between markers

12. **TRACK STATE** `current_slices` updates (Lines 615, 710, 809, 812)
    - **Purpose**: Time-based segment tracking for UI

### **🖱️ UI INTERACTION TRIGGERS** (6 trigger points)

**Files**: `rcy_view.py`, `waveform_view.py`, `commands.py`

13. **Signal Emissions** (rcy_view.py)
    - `add_segment.emit()` / `remove_segment.emit()`
    - **Triggers**: Modifier+click combinations

14. **Split Button Handlers** (rcy_view.py)
    - Split measures/transients buttons
    - **Triggers**: User clicks UI buttons  

15. **Waveform Click Detection** (waveform_view.py)
    - `_on_plot_clicked()` (Lines 406-483)
    - **Triggers**: Mouse clicks with modifiers

16. **Command Pattern** (commands.py)
    - `AddSegmentCommand`, `RemoveSegmentCommand`, `SplitAudioCommand`, `CutAudioCommand`
    - **Triggers**: Undo/redo system execution

### **📊 SEGMENT READING/QUERYING** (4 read operations)

17. **Keyboard Shortcuts** - Read segments for playback (Keys 1-9,0,Q-P)
18. **Mouse Click Playback** - Query segment boundaries for click position  
19. **Export Operations** - Read segments for file export
20. **UI Display** - Read segments for waveform visualization

---

## **🏗️ CURRENT ARCHITECTURE PROBLEMS**

### **Multiple Sources of Truth**:
- `model.segments` (sample-based, authoritative)
- `controller.current_slices` (time-based, UI coordination)  
- `waveform_view.current_slices` (time-based, display)

### **Inconsistent Update Patterns**:
- Some operations update all stores (controller methods)
- Some operations update only model (direct model calls)
- UI state can become stale if not properly synchronized

### **Dual Query Systems**:
- **Keyboard shortcuts**: Direct array indexing (fast, but error-prone)
- **Mouse clicks**: Time-based search (consistent, but slower)

---

## **📋 ANALYSIS SUMMARY**

### **Mutation Categories**:
- **7 Direct Operations** in `audio_processor.py`
- **8 Controller-Coordinated** operations in `rcy_controller.py`
- **6 UI Trigger Points** across view classes and commands
- **4 Read/Query Operations** for playback and display

### **Data Structures Affected**:
1. **`model.segments`** (sample positions) - Source of truth
2. **`controller.current_slices`** (time positions) - UI coordination
3. **`waveform_view.current_slices`** (time positions) - Display

### **Key Insights**:
- All segment mutations ultimately affect `model.segments` array
- Controller acts as coordination layer but doesn't always sync properly
- UI maintains separate state that can become stale
- Keyboard vs mouse input use completely different query logic

---

## **🎯 NEXT STEPS**

This inventory forms the foundation for designing a **centralized SegmentManager** that:

1. **Maintains single source of truth** for all segment data
2. **Updates automatically** when any of the 20+ mutation points trigger
3. **Provides fast query interface** for both keyboard and mouse interactions
4. **Handles coordinate conversion** (samples ↔ time) transparently

**Target Requirements**:
- Sub-millisecond query performance for keyboard shortcuts
- Automatic sync on every segment change
- Unified API for both index-based and time-based queries
- Thread-safe for audio engine access

**Design Phase**: Ready to proceed with SegmentManager architecture design.