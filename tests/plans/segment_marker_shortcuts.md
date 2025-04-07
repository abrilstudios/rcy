# ✅ TEST PLAN: Segment Marker Keyboard Shortcuts (RCY)

## 🧪 Environment

- **OS**: macOS (tested on M1 or Intel)
- **RCY version**: Latest commit with modifier support
- **Audio file**: `amen_classic.wav` (stereo, 44100Hz)
- **View**: Stereo waveform visible, no markers present at start

---

## 🎛 Modifier Behavior Tests

### 1. Add Segment Marker
- ⌨️ Action: `Alt + Click` at 25% along waveform
- ✅ Expected: New vertical slice marker appears at clicked time on both L and R channels

### 2. Remove Segment Marker
- ⌨️ Action: `Alt + Cmd + Click` on existing marker
- ✅ Expected: That marker is removed cleanly
- ❌ No new markers created

### 3. Set Start Marker
- ⌨️ Action: `Shift + Click` at beginning of waveform
- ✅ Expected: Green start marker appears

### 4. Set End Marker
- ⌨️ Action: `Ctrl + Click` near end of waveform
- ✅ Expected: Red end marker appears

---

## 🔁 Combination Tests

### 5. Add Two Segments + Set Range
- Add two segment markers
- Set start (`Shift + Click`) before 1st
- Set end (`Ctrl + Click`) after 2nd
- ✅ Expected: Start and end markers do not interfere with segment markers

### 6. Remove Segment Inside Start/End Range
- Add a few segments
- Define a start/end range
- Remove a segment inside the range
- ✅ Expected: Only the segment is removed, range markers remain

---

## 🧼 Edge Cases

### 7. Modifier Conflict Handling
- ⌨️ Action: `Ctrl + Alt + Click`
- ✅ Expected: No action OR a single defined behavior (log if ambiguous)

### 8. Meta + Click Alone
- ⌨️ Action: `Cmd + Click` (no Alt)
- ✅ Expected: No action — does **not** remove segments (reserved for `Alt + Cmd` only)

---

## 📓 Notes

- Repeat all tests with stereo files and mono files
- Confirm segment visuals are updated in both channels
- Validate marker removal logs if debug output is enabled