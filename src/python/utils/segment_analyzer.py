"""
Segment Analyzer - Tool for analyzing and debugging segments in RCY

This module provides utilities for analyzing segment data in the RCY application,
helping to debug mismatches between the UI, model, and exports.
"""


def visualize_segments(segments: list[int], sample_rate: int, width: int = 80) -> str:
    """
    Create a visual representation of segments to help debug placement issues
    
    Args:
        segments: List of sample positions
        sample_rate: Sample rate of the audio
        width: Width of the visualization in characters
        
    Returns:
        String with a visual representation of the segments
    """
    if not segments or len(segments) < 2:
        return "No segments to visualize"
    
    # Get total length
    total_samples = segments[-1]
    
    # Create a timeline with segment markers
    timeline = [" "] * width
    
    # Add start and end markers
    timeline[0] = "|"
    timeline[-1] = "|"
    
    # Add segment markers
    for segment in segments[1:-1]:  # Skip first and last which are at the edges
        # Scale to visualization width
        position = int((segment / total_samples) * (width - 1))
        # Ensure we're in bounds (should always be, but being safe)
        if 0 <= position < width:
            timeline[position] = "|"
    
    # Convert to string
    timeline_str = "".join(timeline)
    
    # Add time labels
    total_duration = total_samples / sample_rate
    result = []
    result.append(f"0{timeline_str}{total_duration:.2f}s")
    
    # Add positions in seconds below the markers
    positions = []
    for segment in segments:
        second_position = segment / sample_rate
        positions.append(f"{second_position:.2f}s")
    
    result.append(f"Segment positions: {', '.join(positions)}")
    
    # Add segment durations
    durations = []
    for i in range(len(segments) - 1):
        duration = (segments[i+1] - segments[i]) / sample_rate
        durations.append(f"{duration:.2f}s")
    
    result.append(f"Segment durations: {', '.join(durations)}")
    
    return "\n".join(result)

def find_zero_length_segments(segments: list[int]) -> list[int]:
    """
    Identify zero-length segments in the list

    Args:
        segments: List of sample positions

    Returns:
        List of indices where zero-length segments exist
    """
    zero_segments = []

    for i in range(len(segments) - 1):
        if segments[i] == segments[i+1]:
            zero_segments.append(i)

    return zero_segments

def analyze_segments(segments: list[int], sample_rate: int) -> dict[str, any]:
    """
    Perform comprehensive analysis of segment data

    Args:
        segments: List of sample positions
        sample_rate: Sample rate of the audio

    Returns:
        Dictionary with analysis results
    """
    if not segments:
        return {"error": "No segments provided"}

    # Basic stats
    total_segments = len(segments) - 1 if len(segments) > 0 else 0

    # Find zero-length segments
    zero_segments = find_zero_length_segments(segments)
    non_zero_segments = total_segments - len(zero_segments)

    # Calculate durations
    durations = []
    for i in range(len(segments) - 1):
        duration = (segments[i+1] - segments[i]) / sample_rate
        durations.append(duration)

    # Positions in seconds
    positions = [s / sample_rate for s in segments]

    # Create visualization
    visualization = visualize_segments(segments, sample_rate)

    return {
        "total_boundary_points": len(segments),
        "total_segments": total_segments,
        "non_zero_segments": non_zero_segments,
        "zero_segments": len(zero_segments),
        "zero_segment_indices": zero_segments,
        "durations": durations,
        "positions": positions,
        "visualization": visualization
    }

def get_segment_report(segments: list[int], sample_rate: int) -> str:
    """
    Generate a human-readable report for the segments

    Args:
        segments: List of sample positions
        sample_rate: Sample rate of the audio

    Returns:
        String with the report
    """
    analysis = analyze_segments(segments, sample_rate)

    if "error" in analysis:
        return analysis["error"]

    lines = []
    lines.append("====== Segment Analysis Report ======")
    lines.append(f"Total boundary points: {analysis['total_boundary_points']}")
    lines.append(f"Total segments: {analysis['total_segments']}")
    lines.append(f"Non-zero segments: {analysis['non_zero_segments']}")
    lines.append(f"Zero-length segments: {analysis['zero_segments']}")

    if analysis['zero_segments'] > 0:
        lines.append("\nZero-length segments at indices:")
        for idx in analysis['zero_segment_indices']:
            lines.append(f"  - Between points {idx} and {idx+1} (at {analysis['positions'][idx]:.2f}s)")

    lines.append("\nSegment positions (seconds):")
    for i, pos in enumerate(analysis['positions']):
        lines.append(f"  {i}: {pos:.4f}s")

    lines.append("\nSegment durations (seconds):")
    for i, dur in enumerate(analysis['durations']):
        if i in analysis['zero_segment_indices']:
            lines.append(f"  {i}: {dur:.4f}s (ZERO LENGTH)")
        else:
            lines.append(f"  {i}: {dur:.4f}s")

    lines.append("\nVisualization:")
    lines.append(analysis['visualization'])

    return "\n".join(lines)

if __name__ == "__main__":
    # Example usage
    test_segments = [0, 11025, 22050, 22050, 33075, 44100]  # Note the duplicate at index 2-3
    test_rate = 44100
    
    print(get_segment_report(test_segments, test_rate))