"""Tool schemas for TUI commands using Pydantic models."""

from typing import Optional
from pydantic import BaseModel, Field


class SliceTool(BaseModel):
    """Slice audio by measures or transients.

    Args:
        measures: Number of measures to slice into (default mode)
        transients: Transient detection threshold (0-100)
        clear: Clear all existing slices
    """
    measures: Optional[int] = Field(None, description="Number of measures to slice into")
    transients: Optional[int] = Field(None, ge=0, le=100, description="Transient threshold 0-100")
    clear: bool = Field(False, description="Clear all slices")


class PresetTool(BaseModel):
    """Load a breakbeat preset.

    Args:
        preset_id: The ID of the preset to load (e.g., 'amen_classic', 'think_break')
    """
    preset_id: str = Field(..., description="Preset ID to load")


class OpenTool(BaseModel):
    """Open an audio file.

    Args:
        filepath: Path to the audio file
        preset: Optional preset ID to load instead of a file
    """
    filepath: Optional[str] = Field(None, description="Path to audio file")
    preset: Optional[str] = Field(None, description="Preset ID to load")


class MarkersTool(BaseModel):
    """Set L/R markers for selection.

    Args:
        start: Start time in seconds
        end: End time in seconds
        reset: Reset markers to full file
    """
    start: Optional[float] = Field(None, ge=0, description="Start time in seconds")
    end: Optional[float] = Field(None, ge=0, description="End time in seconds")
    reset: bool = Field(False, description="Reset to full file")


class SetTool(BaseModel):
    """Set a configuration value.

    Args:
        setting: Setting name (e.g., 'bars', 'release')
        value: Value to set
    """
    setting: str = Field(..., description="Setting name")
    value: int | float = Field(..., description="Value to set")


class TempoTool(BaseModel):
    """Set or calculate tempo.

    Args:
        bpm: Target BPM for playback
        measures: Calculate tempo from this many measures
    """
    bpm: Optional[float] = Field(None, gt=0, description="Target BPM")
    measures: Optional[int] = Field(None, gt=0, description="Measures for tempo calculation")


class PlayTool(BaseModel):
    """Play a pattern of segments.

    Args:
        pattern: List of segment indices to play (1-based), or all segments if omitted
        loop: Whether to loop the pattern
    """
    pattern: Optional[list[int]] = Field(None, min_length=1, description="Segment indices to play (all if omitted)")
    loop: bool = Field(False, description="Loop the pattern")


class StopTool(BaseModel):
    """Stop playback."""
    pass


class ExportTool(BaseModel):
    """Export sliced samples and SFZ file.

    Args:
        directory: Output directory path
        format: Audio format (wav or flac)
    """
    directory: str = Field(..., description="Output directory")
    format: str = Field("wav", pattern="^(wav|flac)$", description="Audio format")


class ZoomTool(BaseModel):
    """Zoom the waveform view.

    Args:
        direction: 'in' or 'out'
    """
    direction: str = Field(..., pattern="^(in|out)$", description="Zoom direction")


class ModeTool(BaseModel):
    """Set playback mode.

    Args:
        mode: 'loop' or 'oneshot'
    """
    mode: str = Field(..., pattern="^(loop|oneshot)$", description="Playback mode")


class HelpTool(BaseModel):
    """Show help information."""
    pass


class PresetsTool(BaseModel):
    """List available presets."""
    pass


class QuitTool(BaseModel):
    """Exit the application."""
    pass


class CutTool(BaseModel):
    """Cut audio to L/R region in-place.

    Trims the audio file to the region between the L and R markers,
    discarding audio outside this region. The markers are then reset
    to cover the new (trimmed) file.
    """
    pass


class NudgeTool(BaseModel):
    """Nudge the focused marker left or right.

    Args:
        direction: 'left' or 'right'
        mode: 'normal' (1x), 'fine' (0.1x), or 'coarse' (10x)
    """
    direction: str = Field(..., pattern="^(left|right)$", description="Nudge direction")
    mode: str = Field("normal", pattern="^(normal|fine|coarse)$", description="Nudge amount: normal, fine (0.1x), coarse (10x)")


class MarkerTool(BaseModel):
    """Place or move a segment marker at a musical position (bar.beat).

    Position format: X.Y where X is bar (1-based), Y is beat (1-based).
    Examples: 1.1 (start), 2.3 (bar 2, beat 3), 3.1 (bar 3, beat 1)

    The marker is quantized to the grid resolution and clamped to the L/R region.
    If a marker exists nearby, it is moved; otherwise a new one is created.

    Args:
        position: Bar.beat position (e.g., '3.2' for bar 3, beat 2)
    """
    position: str = Field(..., pattern=r"^\d+\.?\d*$", description="Bar.beat position (e.g., '3.2')")


# EP-133 Tools
# ------------
# These tools provide integration with the Teenage Engineering EP-133 K.O. II
# sampler/drum machine. The EP-133 has:
# - 9 projects, 4 banks (A-D) per project, 12 pads per bank = 432 total pads
# - 999 sound slots organized by category (KICK, SNARE, USER1, etc.)

class EP133ConnectTool(BaseModel):
    """Connect to EP-133 K.O. II device.

    Auto-detects MIDI ports. Use this before any other EP-133 operations.
    """
    pass


class EP133DisconnectTool(BaseModel):
    """Disconnect from EP-133 device."""
    pass


class EP133StatusTool(BaseModel):
    """Get EP-133 connection status and port information."""
    pass


class EP133ListSoundsTool(BaseModel):
    """List all sounds currently on the EP-133."""
    pass


class EP133UploadTool(BaseModel):
    """Upload a single segment to an EP-133 sound slot.

    Args:
        slot: Target sound slot (1-999)
        segment: Segment number to upload (1-based)
    """
    slot: int = Field(..., ge=1, le=999, description="Target sound slot (1-999)")
    segment: int = Field(..., ge=1, description="Segment number to upload (1-based)")


class EP133AssignTool(BaseModel):
    """Assign a sound to an EP-133 pad.

    Args:
        project: Project number (1-9)
        group: Pad group/bank (A, B, C, or D)
        pad: Pad number within group (1-12)
        sound_number: Sound slot to assign (1-999)
    """
    project: int = Field(..., ge=1, le=9, description="Project number (1-9)")
    group: str = Field(..., pattern="^[A-Da-d]$", description="Pad group (A-D)")
    pad: int = Field(..., ge=1, le=12, description="Pad number (1-12)")
    sound_number: int = Field(..., ge=1, le=999, description="Sound to assign")


class EP133UploadBankTool(BaseModel):
    """Upload segments to an EP-133 bank and assign to pads.

    This is the high-level command for loading a sliced break onto the EP-133.
    Uploads segments to consecutive sound slots and assigns them to pads 1-12.

    Args:
        project: Project number (1-9)
        bank: Bank/group letter (A, B, C, or D)
        slot_start: Starting sound slot (default: 700 for USER1 category)
        segment_start: First segment to upload (default: 1)
        segment_count: Number of segments to upload (default: all, max 12)
    """
    project: int = Field(1, ge=1, le=9, description="Project number (1-9)")
    bank: str = Field(..., pattern="^[A-Da-d]$", description="Bank/group (A-D)")
    slot_start: int = Field(700, ge=1, le=988, description="Starting sound slot (default: 700)")
    segment_start: int = Field(1, ge=1, description="First segment to upload (default: 1)")
    segment_count: Optional[int] = Field(None, ge=1, le=12, description="Number of segments (max 12)")


class EP133ClearBankTool(BaseModel):
    """Clear all pad assignments in an EP-133 bank.

    Resets pads 1-12 in the specified bank to have no sound assigned.
    Useful for cleanup before/after testing or starting fresh.

    Args:
        project: Project number (1-9)
        bank: Bank/group letter (A, B, C, or D)
    """
    project: int = Field(1, ge=1, le=9, description="Project number (1-9)")
    bank: str = Field(..., pattern="^[A-Da-d]$", description="Bank/group (A-D)")


# Map of tool names to their schemas
TOOL_SCHEMAS = {
    "slice": SliceTool,
    "preset": PresetTool,
    "open": OpenTool,
    "markers": MarkersTool,
    "marker": MarkerTool,
    "set": SetTool,
    "tempo": TempoTool,
    "play": PlayTool,
    "stop": StopTool,
    "export": ExportTool,
    "zoom": ZoomTool,
    "mode": ModeTool,
    "help": HelpTool,
    "presets": PresetsTool,
    "quit": QuitTool,
    "cut": CutTool,
    "nudge": NudgeTool,
    # EP-133 tools
    "ep133_connect": EP133ConnectTool,
    "ep133_disconnect": EP133DisconnectTool,
    "ep133_status": EP133StatusTool,
    "ep133_list_sounds": EP133ListSoundsTool,
    "ep133_upload": EP133UploadTool,
    "ep133_assign": EP133AssignTool,
    "ep133_upload_bank": EP133UploadBankTool,
    "ep133_clear_bank": EP133ClearBankTool,
}

# Aliases for convenience
TOOL_ALIASES = {
    "s": "slice",
    "p": "preset",
    "o": "open",
    "m": "markers",
    "t": "tempo",
    "e": "export",
    "z": "zoom",
    "h": "help",
    "?": "help",
    "q": "quit",
    "x": "stop",
    "c": "cut",
    "n": "nudge",
}
