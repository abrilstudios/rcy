#!/usr/bin/env python3
"""
RX2 Format Reverse Engineering Tool - FIXED VERSION
Analyzes Propellerhead ReCycle RX2 files to understand the binary format
"""

import struct
import sys
from pathlib import Path

class RX2Analyzer:
    def __init__(self, filename):
        self.filename = filename
        with open(filename, 'rb') as f:
            self.data = f.read()
        self.pos = 0
        self.chunks = []
        
    def read_bytes(self, count):
        """Read bytes and advance position"""
        if self.pos + count > len(self.data):
            raise EOFError(f"Trying to read beyond file end: {self.pos + count} > {len(self.data)}")
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result
    
    def read_uint32_be(self):
        """Read 32-bit big-endian unsigned integer"""
        return struct.unpack('>I', self.read_bytes(4))[0]
    
    def read_uint32_le(self):
        """Read 32-bit little-endian unsigned integer"""
        return struct.unpack('<I', self.read_bytes(4))[0]
    
    def read_string(self, length):
        """Read null-terminated string"""
        data = self.read_bytes(length)
        # Find null terminator
        null_pos = data.find(b'\x00')
        if null_pos >= 0:
            return data[:null_pos].decode('ascii', errors='ignore')
        return data.decode('ascii', errors='ignore')
    
    def peek_bytes(self, count):
        """Peek at bytes without advancing position"""
        if self.pos + count > len(self.data):
            return b''
        return self.data[self.pos:self.pos + count]
    
    def hex_dump(self, data, start_pos=0):
        """Show hex dump of data"""
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            print(f"    {start_pos + i:04x}: {hex_part:<48} |{ascii_part}|")
    
    def analyze_chunk(self, chunk_id, size, data):
        """Analyze specific chunk types"""
        print(f"\n--- {chunk_id} chunk (size: {size} bytes) ---")
        
        if chunk_id == 'CREI':
            # Creator information - multiple null-terminated strings
            strings = data.split(b'\x00')
            for i, s in enumerate(strings):
                if s:
                    print(f"  String {i}: '{s.decode('ascii', errors='ignore')}'")
                    
        elif chunk_id == 'GLOB':
            # Global settings
            print(f"  Global settings data:")
            self.hex_dump(data)
            
        elif chunk_id == 'RECY':
            # Main ReCycle data  
            print(f"  Main ReCycle data (showing first 64 bytes):")
            self.hex_dump(data[:64])
            
        elif chunk_id == 'RCYX':
            # Extended ReCycle data
            print(f"  Extended ReCycle data:")
            self.hex_dump(data[:64])
            
        elif chunk_id == 'SLCE':
            # Slice data - this is key!
            print(f"  SLICE DATA:")
            self.hex_dump(data)
            
            # Try to parse slice structure
            if len(data) >= 8:
                pos = 0
                while pos + 4 <= len(data):
                    val = struct.unpack('<I', data[pos:pos+4])[0]
                    print(f"    Offset {pos:02x}: {val:8d} (0x{val:08x})")
                    pos += 4
                    if pos >= 32:  # Don't show too many
                        break
                        
        elif chunk_id.startswith('DEVL') or chunk_id.startswith('EQ') or chunk_id.startswith('COMP'):
            # Audio processing chunks
            print(f"  Audio processing chunk: {chunk_id}")
            self.hex_dump(data[:32])
            
        else:
            # Unknown chunk
            print(f"  Unknown chunk type: {chunk_id}")
            self.hex_dump(data[:32])
    
    def parse_file(self):
        """Parse the entire RX2 file"""
        print(f"Analyzing RX2 file: {self.filename}")
        print(f"File size: {len(self.data)} bytes")
        
        # Read CAT header
        magic = self.read_bytes(4)
        if magic != b'CAT ':
            print(f"ERROR: Invalid magic bytes: {magic}")
            return
        
        container_size = self.read_uint32_be()
        print(f"Container size: {container_size} bytes")
        
        # Check if this is REX2HEAD chunk or direct format type
        next_8_bytes = self.peek_bytes(8)
        if next_8_bytes == b'REX2HEAD':
            # This is a REX2HEAD chunk
            format_type = self.read_bytes(8)  # REX2HEAD
            header_size = self.read_uint32_be()
            header_data = self.read_bytes(header_size)
            print(f"REX2HEAD chunk: {header_size} bytes")
            print(f"Header data:")
            self.hex_dump(header_data)
        else:
            print(f"Unknown format after CAT header: {next_8_bytes}")
            return
        
        # Skip any padding bytes (common in chunk formats)
        while self.pos < len(self.data) and self.data[self.pos] == 0:
            print(f"Skipping padding byte at 0x{self.pos:04x}")
            self.pos += 1
        
        # Now parse the remaining chunks
        chunk_count = 0
        slice_count = 0
        
        while self.pos < len(self.data):
            try:
                # Check if we have enough bytes for a chunk header
                remaining = len(self.data) - self.pos
                if remaining < 8:
                    print(f"Reached end of file, {remaining} bytes remaining")
                    break
                
                chunk_id = self.read_bytes(4).decode('ascii', errors='ignore')
                chunk_size = self.read_uint32_be()
                
                print(f"\nChunk {chunk_count}: '{chunk_id}' (size: {chunk_size} bytes, pos: 0x{self.pos-8:04x})")
                
                # Validate chunk size
                if self.pos + chunk_size > len(self.data):
                    print(f"WARNING: Chunk size {chunk_size} exceeds remaining data ({len(self.data) - self.pos})")
                    break
                
                # Read chunk data
                chunk_data = self.read_bytes(chunk_size)
                
                # Analyze the chunk
                self.analyze_chunk(chunk_id, chunk_size, chunk_data)
                
                if chunk_id == 'SLCE':
                    slice_count += 1
                
                chunk_count += 1
                
                # Safety check
                if chunk_count > 200:
                    print("WARNING: Too many chunks, stopping")
                    break
                    
            except Exception as e:
                print(f"ERROR parsing chunk at position 0x{self.pos:04x}: {e}")
                # Show some context
                context = self.data[max(0, self.pos-16):self.pos+32]
                print("Context:")
                self.hex_dump(context, max(0, self.pos-16))
                break
        
        print(f"\n=== SUMMARY ===")
        print(f"Parsed {chunk_count} chunks total")
        print(f"Found {slice_count} slices")

def main():
    if len(sys.argv) != 2:
        print("Usage: python rx2_analyzer_fixed.py <rx2_file>")
        sys.exit(1)
    
    filename = sys.argv[1]
    if not Path(filename).exists():
        print(f"File not found: {filename}")
        sys.exit(1)
    
    analyzer = RX2Analyzer(filename)
    analyzer.parse_file()

if __name__ == '__main__':
    main()