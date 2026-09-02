"""Headless launch test for the Textual TUI.

Mounts RCYApp with a bundled preset, runs a slice command through the
command input and checks the segment count. Opens the audio output
device the same way the export tests do.
"""
import asyncio

from audio_processor import WavAudioProcessor
from tui.app import RCYApp
from tui.widgets import CommandInput


def test_slice_command_creates_four_segments():
    model = WavAudioProcessor(preset_id="amen_classic")
    app = RCYApp(model=model)

    async def drive() -> int:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#command", CommandInput).focus()
            for char in "/slice 4":
                await pilot.press("space" if char == " " else char)
            await pilot.press("enter")
            await pilot.pause()
            return len(app.segment_manager.get_boundaries()) - 1

    assert asyncio.run(drive()) == 4
