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
        setting: Setting name (e.g., 'bars')
        value: Value to set
    """
    setting: str = Field(..., description="Setting name")
    value: int = Field(..., description="Value to set")


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


# Map of tool names to their schemas
TOOL_SCHEMAS = {
    "slice": SliceTool,
    "preset": PresetTool,
    "open": OpenTool,
    "markers": MarkersTool,
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
}
