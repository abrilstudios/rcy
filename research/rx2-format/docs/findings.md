# RX2 Format Analysis - Initial Findings

## File Structure Discovered

### Header (CAT Container)
```
00: CAT [4 bytes] - Container format identifier  
04: Size [4 bytes BE] - Total container size
08: REX2HEAD [8 bytes] - Format identifier
10: Header size [4 bytes BE] - Size of REX2HEAD data  
14: Header data [variable] - Unknown purpose
```

### Chunks Found

#### 1. CREI (Creator Information)
**Size**: 122 bytes  
**Content**: Multiple null-terminated strings
- "Propellerhead Software AB"
- "Copyright (c) 2000-2003" 
- "http://www.propellerheads.se"
- "maingate@propellerheads.se"

#### 2. GLOB (Global Settings) 
**Size**: 22 bytes  
**Raw data**: `00 00 00 47 00 02 00 04 04 41 00 00 03 e8 00 00 00 01 88 2d 01 00`

**Possible interpretations**:
- `00 00 00 47` = 71 (sample rate related?)
- `00 02` = 2 (stereo channels?)
- `00 04` = 4 (beats per measure?)
- `04 41` = 1089 (unknown)
- `00 00 03 e8` = 1000 (tempo * 10? = 100.0 BPM?)
- `88 2d` = 34861 (sample related?)

#### 3. RECY (Main ReCycle Data)
**Size**: 15 bytes  
**Raw data**: `bc 02 00 00 00 01 00 00 18 bb 00 00 00 00 21`

**Possible interpretations**:
- `bc 02` = 700 (unknown)
- `00 01` = 1 (version?)
- `18 bb` = 6331 (sample count related?)

## Key Insights

1. **Chunk-based format** similar to IFF/RIFF
2. **Padding bytes** used for alignment
3. **Global settings** stored in GLOB chunk
4. **Creator info** preserved in CREI
5. **Main data** in RECY chunk
6. **No SLCE chunks found yet** - might be in nested containers

## Next Steps

1. Fix parsing of remaining chunks (handle malformed chunk IDs)
2. Analyze GLOB chunk structure for tempo/timing info
3. Find the slice data (SLCE chunks)
4. Locate audio data storage
5. Map timing relationships

## Hypothesis

The RX2 format stores:
- **Metadata** in GLOB (tempo, measures, sample rate)
- **Slice boundaries** in SLCE chunks (not found yet)
- **Audio data** somewhere in the file (possibly embedded)
- **Creator info** for compatibility tracking