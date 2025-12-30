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
        preset_id: The ID of the preset to load (e.g., 'amen_classic', 'apache_break')
    """
    preset_id: str = Field(..., description="Preset ID to load")


class ImportTool(BaseModel):
    """Import an audio file into the current view.

    Loads a WAV file directly without preset metadata. The file must be 44100Hz.

    Args:
        filepath: Path to WAV file to import
    """
    filepath: str = Field(..., description="Path to WAV file to import")


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


class SkinTool(BaseModel):
    """Switch or list color skins.

    Args:
        skin_name: Skin name to switch to, or 'list' to show available skins (default: list)
    """
    skin_name: str = Field("list", description="Skin name or 'list'")


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


# EP-133 Tool
# -----------
# Unified command for Teenage Engineering EP-133 K.O. II integration.
# Subcommands: connect, disconnect, status, set, list, upload, clear

class EP133Tool(BaseModel):
    """EP-133 K.O. II sampler integration.

    Subcommands:
        connect              Connect to EP-133 (auto-detects MIDI)
        disconnect           Disconnect from EP-133
        status               Show connection status
        set project <1-9>    Set target project (match your EP-133 selection)
        list                 List sounds on device
        upload <bank> <slot> Upload segments to bank (A/B/C/D) starting at slot
        clear <bank>         Clear pad assignments in bank

    Examples:
        /ep133 connect
        /ep133 set project 9   Set target to project 9
        /ep133 upload A 700    Upload to bank A starting at slot 700
        /ep133 clear A
    """
    subcommand: str = Field(..., description="Subcommand: connect, disconnect, status, set, list, upload, clear")
    arg1: Optional[str] = Field(None, description="First argument (e.g., 'project' for set, bank letter for upload/clear)")
    arg2: Optional[str] = Field(None, description="Second argument (e.g., project number, slot number)")
    slot: Optional[int] = Field(None, ge=1, le=988, description="Starting slot for upload")


class ViewTool(BaseModel):
    """Switch notebook page view.

    The TUI has three pages that behave like a notebook:
    - waveform: Audition and temporal reasoning (default)
    - bank: EP-133 pad layout (4 banks × 12 pads)
    - sounds: Full sound inventory (999 slots)

    Args:
        page: Page to switch to (waveform, bank, sounds)
        bank: For bank page, which bank to focus (A/B/C/D)
    """
    page: str = Field(..., pattern="^(waveform|bank|sounds)$", description="Page: waveform, bank, or sounds")
    bank: Optional[str] = Field(None, pattern="^[A-Da-d]$", description="Bank to focus (A/B/C/D)")


class PickTool(BaseModel):
    """Pick up a sound from the current context.

    On Sounds page: picks the focused sound
    On Waveform page: picks the current slice as a sound
    On Bank page: picks the sound assigned to focused pad
    """
    pass


class DropTool(BaseModel):
    """Drop the held sound onto the current target.

    On Bank page: assigns held sound to focused pad
    On Sounds page: copies held sound to focused empty slot
    """
    pass


# Map of tool names to their schemas
TOOL_SCHEMAS = {
    "slice": SliceTool,
    "preset": PresetTool,
    "import": ImportTool,
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
    "skin": SkinTool,
    "cut": CutTool,
    "nudge": NudgeTool,
    # EP-133 unified command
    "ep133": EP133Tool,
    # Notebook pages
    "view": ViewTool,
    "pick": PickTool,
    "drop": DropTool,
}

# Aliases for convenience
TOOL_ALIASES = {
    "s": "slice",
    "p": "preset",
    "i": "import",
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
    "v": "view",
}
