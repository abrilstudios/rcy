"""ASCII waveform renderer for TUI display."""

import numpy as np
from typing import Optional

from rich.text import Text

from tui.skin_manager import get_skin_manager

# Block characters for waveform amplitude (8 levels)
BLOCKS = " ▁▂▃▄▅▆▇█"


def render_waveform(
    audio_data: np.ndarray,
    width: int = 70,
    height: int = 2,
    sample_rate: int = 44100,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    slices: Optional[list[float]] = None,
    start_marker: float = 0.0,
    end_marker: Optional[float] = None,
    focused_marker: Optional[str] = None,
    segment_marker_positions: Optional[list[float]] = None,
) -> list[str]:
    """Render audio data as ASCII waveform.

    Args:
        audio_data: Mono audio samples (or left channel of stereo)
        width: Character width of the waveform display
        height: Number of rows for waveform (1 or 2)
        sample_rate: Audio sample rate
        start_time: Start time of visible window
        end_time: End time of visible window (None = full duration)
        slices: List of slice positions in seconds
        start_marker: L marker position in seconds
        end_marker: R marker position in seconds (None = end of file)
        focused_marker: ID of the currently focused marker (e.g., "L", "R", "seg_01")
        segment_marker_positions: List of segment marker positions (seconds)

    Returns:
        List of strings representing the waveform rows
    """
    if len(audio_data) == 0:
        return ["─" * width] * height

    total_duration = len(audio_data) / sample_rate
    if end_time is None:
        end_time = total_duration
    if end_marker is None:
        end_marker = total_duration

    # Calculate samples per character column
    visible_samples = int((end_time - start_time) * sample_rate)
    start_sample = int(start_time * sample_rate)
    samples_per_col = max(1, visible_samples // width)

    lines = []

    # Build slice marker row
    slice_row = _build_marker_row(
        width, start_time, end_time, slices, start_marker, end_marker,
        focused_marker, segment_marker_positions
    )
    lines.append(slice_row)

    # Build waveform rows
    for row_idx in range(height):
        row_chars = []
        for col in range(width):
            col_start = start_sample + col * samples_per_col
            col_end = min(col_start + samples_per_col, len(audio_data))

            if col_start >= len(audio_data):
                row_chars.append(" ")
                continue

            chunk = audio_data[col_start:col_end]
            if len(chunk) == 0:
                row_chars.append(" ")
                continue

            # Get peak amplitude for this column
            peak = np.max(np.abs(chunk))

            # Map to block character (0-8 levels)
            level = int(peak * 8)
            level = min(level, 8)
            row_chars.append(BLOCKS[level])

        lines.append("".join(row_chars))

    # Build segment number row
    segment_row = _build_segment_row(width, start_time, end_time, slices)
    lines.append(segment_row)

    # Build time axis row
    time_row = _build_time_row(width, start_time, end_time)
    lines.append(time_row)

    return lines


def _build_marker_row(
    width: int,
    start_time: float,
    end_time: float,
    slices: Optional[list[float]],
    start_marker: float,
    end_marker: float,
    focused_marker: Optional[str] = None,
    segment_marker_positions: Optional[list[float]] = None,
) -> str:
    """Build the row showing L/R markers and slice positions.

    Args:
        width: Width of the display in characters
        start_time: Start of visible window (seconds)
        end_time: End of visible window (seconds)
        slices: List of slice/segment positions (seconds)
        start_marker: L marker position (seconds)
        end_marker: R marker position (seconds)
        focused_marker: ID of focused marker (e.g., "L", "R", "seg_01")
        segment_marker_positions: List of segment marker positions (seconds) for focus indication
    """
    row = [" "] * width
    duration = end_time - start_time
    if duration <= 0:
        return "".join(row)

    def time_to_col(t: float) -> int:
        return int((t - start_time) / duration * (width - 1))

    # Place L marker - show as [L] if focused
    if start_time <= start_marker <= end_time:
        col = time_to_col(start_marker)
        if 0 <= col < width:
            if focused_marker == "L":
                # Show focused L marker with brackets
                # If at left edge, shift right to fit [L]
                if col < 1:
                    col = 1
                if col > 0:
                    row[col - 1] = "["
                row[col] = "L"
                if col < width - 1:
                    row[col + 1] = "]"
            else:
                row[col] = "L"

    # Place R marker - show as [R] if focused
    if start_time <= end_marker <= end_time:
        col = time_to_col(end_marker)
        if 0 <= col < width:
            if focused_marker == "R":
                # Show focused R marker with brackets
                # If at right edge, shift left to fit [R]
                if col >= width - 1:
                    col = width - 2
                if col > 0 and row[col - 1] == " ":
                    row[col - 1] = "["
                row[col] = "R"
                if col < width - 1:
                    row[col + 1] = "]"
            else:
                row[col] = "R"

    # Place segment markers (from MarkerManager)
    if segment_marker_positions:
        for i, seg_time in enumerate(segment_marker_positions):
            if start_time < seg_time < end_time:
                col = time_to_col(seg_time)
                if 0 <= col < width and row[col] == " ":
                    seg_id = f"seg_{i+1:02d}"
                    if focused_marker and focused_marker.startswith("seg_"):
                        # Check if this segment is focused by comparing positions
                        # (a bit hacky but works for now)
                        row[col] = "◆" if focused_marker == seg_id else "▼"
                    else:
                        row[col] = "▼"

    # Place slice markers (legacy - from segment_manager)
    if slices:
        for slice_time in slices:
            if start_time < slice_time < end_time:
                col = time_to_col(slice_time)
                if 0 <= col < width and row[col] == " ":
                    row[col] = "▼"

    return "".join(row)


def _build_segment_row(
    width: int,
    start_time: float,
    end_time: float,
    slices: Optional[list[float]],
) -> str:
    """Build row showing segment numbers."""
    if not slices or len(slices) < 2:
        return " " * width

    row = [" "] * width
    duration = end_time - start_time
    if duration <= 0:
        return "".join(row)

    def time_to_col(t: float) -> int:
        return int((t - start_time) / duration * (width - 1))

    # Place segment numbers at midpoint of each segment
    for i in range(len(slices) - 1):
        seg_start = slices[i]
        seg_end = slices[i + 1]
        seg_mid = (seg_start + seg_end) / 2

        if start_time <= seg_mid <= end_time:
            col = time_to_col(seg_mid)
            seg_num = i + 1

            # Format segment number
            if seg_num <= 10:
                label = str(seg_num % 10)  # 1-9, 0 for 10
            elif seg_num <= 20:
                # q-p keys
                label = "qwertyuiop"[seg_num - 11]
            else:
                label = "·"

            if 0 <= col < width:
                row[col] = label

    return "".join(row)


def _build_time_row(width: int, start_time: float, end_time: float) -> str:
    """Build the time axis row."""
    start_str = f"{start_time:.2f}s"
    end_str = f"{end_time:.2f}s"
    mid_time = (start_time + end_time) / 2
    mid_str = f"{mid_time:.2f}s"

    # Calculate positions
    mid_col = width // 2 - len(mid_str) // 2
    end_col = width - len(end_str)

    row = [" "] * width

    # Place start time
    for i, c in enumerate(start_str):
        if i < width:
            row[i] = c

    # Place mid time (if room)
    if mid_col > len(start_str) + 2 and mid_col + len(mid_str) < end_col - 2:
        for i, c in enumerate(mid_str):
            if mid_col + i < width:
                row[mid_col + i] = c

    # Place end time
    for i, c in enumerate(end_str):
        if end_col + i < width:
            row[end_col + i] = c

    return "".join(row)


def format_display(
    filename: str,
    bpm: float,
    bars: int,
    num_slices: int,
    waveform_lines: list[str],
    width: int = 70,
) -> Text:
    """Format complete TUI display with borders and skin colors.

    Args:
        filename: Audio filename
        bpm: Detected/set tempo
        bars: Number of bars/measures
        num_slices: Number of slice segments
        waveform_lines: Output from render_waveform()
        width: Display width

    Returns:
        Rich Text object with colored display
    """
    skin = get_skin_manager()

    # Get colors from skin
    border_color = skin.get_color("border", "normal")
    filename_color = skin.get_color("header", "filename")
    bpm_color = skin.get_color("header", "bpm")
    info_color = skin.get_color("header", "info")
    waveform_color = skin.get_color("waveform", "foreground")
    marker_l_color = skin.get_color("markers", "L")
    marker_r_color = skin.get_color("markers", "R")
    marker_seg_color = skin.get_color("markers", "segment")
    marker_focused_color = skin.get_color("markers", "focused")
    segment_color = skin.get_color("segments", "number")
    time_color = skin.get_color("time_axis", "foreground")

    result = Text()

    # Top border
    result.append("┌" + "─" * (width - 2) + "┐\n", style=border_color)

    # Header line
    result.append("│", style=border_color)
    result.append(f" {filename}", style=filename_color)
    result.append(f"  {bpm:.1f} BPM", style=bpm_color)
    result.append(f"  {bars} bars  {num_slices} slices", style=info_color)
    # Pad and close
    header_content = f" {filename}  {bpm:.1f} BPM  {bars} bars  {num_slices} slices"
    padding = " " * max(0, width - 2 - len(header_content))
    result.append(padding)
    result.append("│\n", style=border_color)

    # Separator
    result.append("├" + "─" * (width - 2) + "┤\n", style=border_color)

    # Waveform lines with coloring
    for i, wf_line in enumerate(waveform_lines):
        result.append("│", style=border_color)

        padded = wf_line[:width - 2].ljust(width - 2)

        if i == 0:
            # Marker row - color L, R, and segment markers
            _append_marker_row(result, padded, marker_l_color, marker_r_color,
                               marker_seg_color, marker_focused_color)
        elif i in (1, 2):
            # Waveform rows
            result.append(padded, style=waveform_color)
        elif i == 3:
            # Segment number row
            result.append(padded, style=segment_color)
        elif i == 4:
            # Time axis row
            result.append(padded, style=time_color)
        else:
            result.append(padded)

        result.append("│\n", style=border_color)

    # Bottom border
    result.append("└" + "─" * (width - 2) + "┘", style=border_color)

    return result


def _append_marker_row(
    text: Text,
    row: str,
    l_color: str,
    r_color: str,
    seg_color: str,
    focused_color: str
) -> None:
    """Append marker row with appropriate colors for each marker type."""
    i = 0
    while i < len(row):
        char = row[i]

        # Check for focused marker patterns [L] or [R]
        if char == '[' and i + 2 < len(row):
            if row[i + 1] == 'L' and row[i + 2] == ']':
                text.append("[L]", style=focused_color)
                i += 3
                continue
            elif row[i + 1] == 'R' and row[i + 2] == ']':
                text.append("[R]", style=focused_color)
                i += 3
                continue

        # Color individual markers
        if char == 'L':
            text.append(char, style=l_color)
        elif char == 'R':
            text.append(char, style=r_color)
        elif char in ('▼', '◆'):
            # ◆ is focused segment marker
            if char == '◆':
                text.append(char, style=focused_color)
            else:
                text.append(char, style=seg_color)
        else:
            text.append(char)

        i += 1
