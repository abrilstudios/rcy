#!/usr/bin/env python3
"""
RX2 Format Reverse Engineering Tool
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
    
    def analyze_chunk(self, chunk_id, size):
        """Analyze specific chunk types"""
        start_pos = self.pos
        
        print(f"\n--- Analyzing {chunk_id} chunk (size: {size} bytes) ---")
        
        if chunk_id == 'CREI':
            # Creator information
            self.analyze_creator_chunk(size)
        elif chunk_id == 'GLOB':
            # Global settings
            self.analyze_global_chunk(size)
        elif chunk_id == 'RECY':
            # Main ReCycle data
            self.analyze_recy_chunk(size)
        elif chunk_id == 'RCYX':
            # Extended ReCycle data
            self.analyze_rcyx_chunk(size)
        elif chunk_id == 'SLCE':
            # Slice data
            self.analyze_slice_chunk(size)
        else:
            # Unknown chunk - show hex dump
            print(f"Unknown chunk type: {chunk_id}")
            self.hex_dump(min(size, 64))
        
        # Ensure we read the entire chunk
        bytes_read = self.pos - start_pos
        if bytes_read < size:
            remaining = size - bytes_read
            print(f"Skipping {remaining} remaining bytes in {chunk_id} chunk")
            self.pos += remaining
    
    def analyze_creator_chunk(self, size):
        """Analyze CREI (creator) chunk"""
        data = self.read_bytes(size)
        # CREI contains multiple null-terminated strings
        strings = data.split(b'\x00')
        for i, s in enumerate(strings):
            if s:
                print(f"  String {i}: {s.decode('ascii', errors='ignore')}")
    
    def analyze_global_chunk(self, size):
        """Analyze GLOB (global settings) chunk"""
        print(f"  Raw data ({size} bytes):")
        self.hex_dump(size)
    
    def analyze_recy_chunk(self, size):
        """Analyze RECY (main ReCycle data) chunk"""
        print(f"  Raw data ({size} bytes):")
        self.hex_dump(min(size, 32))  # Show first 32 bytes
        self.pos += size - min(size, 32)  # Skip the rest for now
    
    def analyze_rcyx_chunk(self, size):
        """Analyze RCYX (extended ReCycle data) chunk"""
        print(f"  Raw data ({size} bytes):")
        self.hex_dump(min(size, 32))
        self.pos += size - min(size, 32)
    
    def analyze_slice_chunk(self, size):
        """Analyze SLCE (slice) chunk"""
        print(f"  Slice data ({size} bytes):")
        # Try to interpret slice data
        if size >= 8:
            # Maybe slice timing info?
            val1 = self.read_uint32_le()
            val2 = self.read_uint32_le() 
            print(f"    Possible timing: {val1}, {val2}")
            remaining = size - 8
            if remaining > 0:
                print(f"    Additional data ({remaining} bytes):")
                self.hex_dump(min(remaining, 16))
                self.pos += remaining - min(remaining, 16)
        else:
            self.hex_dump(size)
    
    def hex_dump(self, count):
        """Show hex dump of next count bytes"""
        data = self.read_bytes(count)
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            print(f"    {i:04x}: {hex_part:<48} |{ascii_part}|")
    
    def parse_file(self):
        """Parse the entire RX2 file"""
        print(f"Analyzing RX2 file: {self.filename}")
        print(f"File size: {len(self.data)} bytes")
        
        # Read initial header
        magic = self.read_bytes(4)
        if magic != b'CAT ':
            print(f"ERROR: Invalid magic bytes: {magic}")
            return
        
        file_size = self.read_uint32_be()
        print(f"Container size: {file_size} bytes")
        
        format_type = self.read_bytes(8)
        print(f"Format type: {format_type}")
        
        if format_type != b'REX2HEAD':
            print(f"ERROR: Not a REX2 file: {format_type}")
            return
        
        # REX2HEAD chunk has its own size
        header_size = self.read_uint32_be()
        print(f"REX2HEAD chunk size: {header_size} bytes")
        
        # Skip the header data for now
        print(f"Skipping REX2HEAD data ({header_size} bytes)")
        header_data = self.read_bytes(header_size)
        print(f"REX2HEAD data preview:")
        for i in range(0, min(len(header_data), 32), 16):
            chunk = header_data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            print(f"  {i:04x}: {hex_part:<48} |{ascii_part}|")
        
        # Parse chunks
        chunk_count = 0
        while self.pos < len(self.data):
            try:
                # Check if we have enough bytes for a chunk header
                if self.pos + 8 > len(self.data):
                    print(f"Reached end of file at position {self.pos}")
                    break
                
                chunk_id = self.read_bytes(4).decode('ascii', errors='ignore')
                chunk_size = self.read_uint32_be()
                
                print(f"\nChunk {chunk_count}: '{chunk_id}' (size: {chunk_size} bytes)")
                
                # Validate chunk size
                if self.pos + chunk_size > len(self.data):
                    print(f"WARNING: Chunk size {chunk_size} exceeds remaining data")
                    break
                
                # Analyze the chunk
                self.analyze_chunk(chunk_id, chunk_size)
                chunk_count += 1
                
                # Safety check
                if chunk_count > 100:
                    print("WARNING: Too many chunks, stopping")
                    break
                    
            except Exception as e:
                print(f"ERROR parsing chunk at position {self.pos}: {e}")
                break
        
        print(f"\nParsed {chunk_count} chunks total")

def main():
    if len(sys.argv) != 2:
        print("Usage: python rx2_analyzer.py <rx2_file>")
        sys.exit(1)
    
    filename = sys.argv[1]
    if not Path(filename).exists():
        print(f"File not found: {filename}")
        sys.exit(1)
    
    analyzer = RX2Analyzer(filename)
    analyzer.parse_file()

if __name__ == '__main__':
    main()