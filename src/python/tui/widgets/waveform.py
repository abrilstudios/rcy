"""Waveform display widget for Textual TUI."""

from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text

from tui.waveform import render_waveform, format_display


class WaveformWidget(Widget):
    """ASCII waveform display with markers and segments.

    This widget displays the audio waveform using Unicode block characters,
    along with L/R markers, slice positions, segment numbers, and time axis.
    """

    DEFAULT_CSS = """
    WaveformWidget {
        height: auto;
    }
    """

    # Reactive attributes - changes trigger re-render
    filename: reactive[str] = reactive("")
    bpm: reactive[float] = reactive(0.0)
    bars: reactive[int] = reactive(1)
    num_slices: reactive[int] = reactive(0)

    def __init__(
        self,
        audio_data=None,
        sample_rate: int = 44100,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._audio_data = audio_data
        self._sample_rate = sample_rate
        self._start_time = 0.0
        self._end_time: float | None = None
        self._slices: list[float] | None = None
        self._start_marker = 0.0
        self._end_marker: float | None = None

    def set_audio_data(self, audio_data, sample_rate: int = 44100) -> None:
        """Update the audio data to display."""
        self._audio_data = audio_data
        self._sample_rate = sample_rate
        self.refresh()

    def set_markers(self, start: float, end: float) -> None:
        """Set L/R marker positions."""
        self._start_marker = start
        self._end_marker = end
        self.refresh()

    def set_slices(self, slices: list[float]) -> None:
        """Set slice positions in seconds."""
        self._slices = slices
        self.num_slices = len(slices) - 1 if slices else 0
        self.refresh()

    def set_view_range(self, start: float, end: float) -> None:
        """Set the visible time range (for zoom)."""
        self._start_time = start
        self._end_time = end
        self.refresh()

    def render(self) -> Text:
        """Render the waveform display."""
        # Get available width (account for borders)
        width = self.size.width - 2 if self.size.width > 4 else 70

        if self._audio_data is None or len(self._audio_data) == 0:
            # Show placeholder when no audio
            lines = [
                "┌" + "─" * (width - 2) + "┐",
                "│" + " No audio loaded ".center(width - 2) + "│",
                "│" + " Use /preset or /open ".center(width - 2) + "│",
                "└" + "─" * (width - 2) + "┘",
            ]
            return Text("\n".join(lines))

        # Render waveform using existing function
        waveform_lines = render_waveform(
            audio_data=self._audio_data,
            width=width - 2,  # Account for box borders
            height=2,
            sample_rate=self._sample_rate,
            start_time=self._start_time,
            end_time=self._end_time,
            slices=self._slices,
            start_marker=self._start_marker,
            end_marker=self._end_marker,
        )

        # Format with borders using existing function
        display = format_display(
            filename=self.filename or "No file",
            bpm=self.bpm,
            bars=self.bars,
            num_slices=self.num_slices,
            waveform_lines=waveform_lines,
            width=width,
        )

        return Text(display)
