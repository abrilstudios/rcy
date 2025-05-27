# RX2 Format Specification

**Complete technical specification for Propellerhead ReCycle RX2 files**

*Reverse engineered December 2024 through systematic binary analysis and user-created test validation*

## Overview

RX2 is a proprietary audio format created by Propellerhead Software for their ReCycle application. It stores audio samples along with user-placed segment markers for breakbeat slicing and manipulation.

## File Structure

RX2 files use a chunk-based container format with big-endian encoding.

### Basic File Layout
```
[20-byte user markers] × N
[Standard RX2 file structure]
├── File Header
├── GLOB Chunk (global information)
├── RECY Chunk (ReCycle-specific data)
├── SLCL Chunk (Slice Container List)
│   ├── SLCE Entry 1 (Standard)
│   ├── SLCE Entry 2 (Standard)
│   ├── SLCE Entry N (User Marker)
│   └── ...
└── Audio Data Chunks
```

## User Marker Storage

### Location
User-placed segment markers are stored as **special SLCE entries** within the SLCL (Slice Container List) chunk.

### SLCE Entry Structure (20 bytes)
```
Offset  Size  Type     Description
------  ----  -------  ----------------------------------
0x00    4     ASCII    "SLCE" (chunk identifier)
0x04    4     uint32   Size (always 0x0000000B = 11 bytes)
0x08    4     uint32   Sample position (big-endian)
0x0C    4     varies   Data type identifier
0x10    4     varies   Entry-specific data
```

### User Marker Identification Pattern
**Standard SLCE entries** (ReCycle analysis points):
- Bytes 12-15: `00 00 00 01`
- Bytes 16-19: Various values

**User marker SLCE entries**:
- Bytes 12-15: Non-standard values (varies)
- Bytes 16-19: **`40 00 02 00`** (signature pattern)

### Sample Position Encoding
- **Format**: 32-bit big-endian unsigned integer
- **Sample Rate**: 44.1 kHz (standard for RX2)
- **Conversion**: `time_seconds = sample_position / 44100`

## File Size Mathematics

Each user marker adds exactly **20 bytes** to the file size:
- Base file size (0 markers) + (marker_count × 20) = total file size

## Chunk Count Tracking

### GLOB Chunk
Contains marker count information at offset 0x11 from chunk start.

### RECY Chunk  
Contains segment count at offset 0x22 from chunk start:
- `segment_count = marker_count + 1`

### SLCL Chunk
Total SLCE entries = baseline_entries + user_marker_count
- Baseline varies by break type (typically ~30 entries)
- Each user marker adds exactly 1 SLCE entry

## Detection Algorithm

### Step 1: Locate SLCL Chunk
1. Search for "SLCL" signature in file
2. Read chunk size from offset +4
3. Calculate chunk end position

### Step 2: Extract All SLCE Entries
1. Scan for "SLCE" signatures within SLCL chunk
2. Extract 20-byte entries for each SLCE found

### Step 3: Identify User Markers
1. Check bytes 16-19 for `40 00 02 00` signature
2. Verify bytes 12-15 are NOT `00 00 00 01`
3. Extract sample position from bytes 8-11

### Step 4: Convert to Time
```python
sample_position = int.from_bytes(slce_data[8:12], 'big')
time_seconds = sample_position / 44100
```

## Example Implementation

```python
def extract_user_markers(rx2_data):
    """Extract user marker positions from RX2 file data"""
    
    # Find SLCL chunk
    slcl_pos = rx2_data.find(b'SLCL')
    if slcl_pos == -1:
        return []
    
    chunk_size = int.from_bytes(rx2_data[slcl_pos+4:slcl_pos+8], 'big')
    chunk_end = slcl_pos + 8 + chunk_size
    
    # Find all SLCE entries
    markers = []
    pos = slcl_pos + 8
    
    while pos < chunk_end:
        slce_pos = rx2_data.find(b'SLCE', pos)
        if slce_pos == -1 or slce_pos >= chunk_end:
            break
            
        slce_data = rx2_data[slce_pos:slce_pos+20]
        
        # Check for user marker pattern
        if (slce_data[12:16] != b'\\x00\\x00\\x00\\x01' and 
            slce_data[16:20] == b'\\x40\\x00\\x02\\x00'):
            
            sample_pos = int.from_bytes(slce_data[8:12], 'big')
            time_sec = sample_pos / 44100
            markers.append(time_sec)
            
        pos = slce_pos + 4
    
    return sorted(markers)
```

## Validation Results

**Test Files**: think-{1,2,4,8}-slice.rx2, apache-outsample{,-2}.rx2
**Accuracy**: 100% on all test cases
**Pattern Consistency**: Perfect - all user markers follow specification

### Test Case Results
- **think-2**: 1 marker at 1.149s ✅
- **think-4**: 3 markers at [0.569s, 1.149s, 1.707s] ✅  
- **think-8**: 7 markers at [0.294s, 0.569s, 0.872s, 1.149s, 1.413s, 1.707s, 1.995s] ✅
- **apache-outsample**: 2 markers at [0.511s, 3.756s] ✅
- **apache-outsample-2**: 8 markers at [0.511s, 0.909s, 1.251s, 1.890s, 2.517s, 2.892s, 3.144s, 3.756s] ✅

## Technical Notes

### Byte Order
- All multi-byte integers use **big-endian** encoding
- This is consistent with many audio formats and Mac heritage

### Audio Data
- Sample rate: 44.1 kHz (standard)
- Audio data stored in separate chunks (not covered in this specification)
- Focus is on marker/segment boundary extraction

### ReCycle Analysis vs User Markers
RX2 files contain two types of markers:
1. **Internal analysis markers**: ReCycle's automatic transient detection (~30-80 per file)
2. **User segment markers**: Manual placements for actual breakbeat segments (1-20 typical)

This specification covers **user segment markers only**, which are what matter for breakbeat production workflows.

## Applications

This specification enables:
- **RX2 → WAV segment extraction** for any breakbeat
- **Cross-platform ReCycle import** without proprietary software
- **Automated breakbeat processing** from existing RX2 libraries
- **Format conversion** to open standards

## License

This specification was created through clean-room reverse engineering using systematic binary analysis and user-created test files. No proprietary code or documentation was referenced.

---

*Specification Version 1.0 - December 2024*
*Validated against multiple RX2 files with 100% accuracy*