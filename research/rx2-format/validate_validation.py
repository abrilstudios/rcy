#\!/usr/bin/env python3
"""
Generic RX2 validation script for validation dataset
"""

import json
import sys
from pathlib import Path

# Add the research directory to path
sys.path.append('.')
from test_unknown_data_hypothesis import extract_non_standard_unknown_markers

def validate_validation_dataset():
    """Validate algorithm performance on validation dataset"""
    
    # Load metadata
    datasets_path = Path('./datasets')
    metadata_path = datasets_path / 'validation' / 'metadata.json'
    
    with open(metadata_path, 'r') as f:
        split_data = json.load(f)
    
    print(f"=== VALIDATION DATASET VALIDATION ===")
    print(f"Description: {split_data['description']}")
    print()
    
    total_files = 0
    perfect_matches = 0
    
    for file_info in split_data['files']:
        filename = file_info['file']
        expected_markers = file_info['expected_markers']
        expected_segments = file_info['expected_segments']
        
        filepath = datasets_path / 'validation' / 'rx2' / filename
        
        if not filepath.exists():
            print(f"{filename}: FILE NOT FOUND")
            continue
            
        markers = extract_non_standard_unknown_markers(str(filepath))
        total_files += 1
        
        if markers is None:
            print(f"{filename}: EXTRACTION FAILED")
            continue
            
        found_markers = len(markers)
        found_segments = found_markers + 1
        
        marker_match = found_markers == expected_markers
        segment_match = found_segments == expected_segments
        
        if marker_match and segment_match:
            perfect_matches += 1
            status = "✅ PERFECT"
        else:
            status = "❌ MISMATCH"
        
        print(f"{filename}:")
        print(f"  Expected: {expected_markers} markers, {expected_segments} segments")
        print(f"  Found:    {found_markers} markers, {found_segments} segments {status}")
        print(f"  Purpose: {file_info['purpose']}")
        print()
    
    accuracy = (perfect_matches / total_files * 100) if total_files > 0 else 0
    print(f"=== VALIDATION RESULTS ===")
    print(f"Perfect matches: {perfect_matches}/{total_files}")
    print(f"Accuracy: {accuracy:.1f}%")
    
    return accuracy == 100.0

if __name__ == "__main__":
    success = validate_validation_dataset()
    sys.exit(0 if success else 1)
