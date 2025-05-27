# RX2 Format Reverse Engineering

**PRIVATE RESEARCH** - Not for public distribution until proven

## Objective
Reverse engineer the Propellerhead ReCycle RX2 format to:
1. Extract slice boundary data from RX2 files
2. Access embedded audio data
3. Preserve tempo and timing metadata
4. Enable import of classic breakbeat libraries

## Test File
- `funky_drummer.rx2` - James Brown "Funky Drummer" break
- 513,246 bytes, contains multiple slices
- Reference for validating our parser

## Research Notes
- RX2 uses IFF/RIFF-like chunk format
- Contains audio data + slice metadata in single file
- Propellerhead format from 2000-2003 era
- No existing open source parsers for RX2 (only older REX format)

## Potential Impact
- Unlock hundreds of classic breaks from rhythm-lab.com archive
- Provide reference for RCY native format design
- Make lost breakbeat history accessible again

## Status
🔬 **Research Phase** - Binary format analysis in progress