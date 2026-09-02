"""Shared `--preset | --input` source arguments for the headless CLIs."""

from __future__ import annotations

import argparse
import os
import pathlib

from config_manager import config
from kit_manifest import SourceAudio, load_source_audio

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent


class CliError(Exception):
    """A usage or input error, printed as `error: ...` with exit status 2."""


def add_source_arguments(group: argparse._ActionsContainer) -> None:
    group.add_argument("--preset", "-p", help="Preset id from config/presets (e.g. apache_break)")
    group.add_argument("--input", "-i", help="Path to a 44100 Hz WAV file")


def add_measures_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--measures", "-m", type=int,
        help="Number of 4/4 measures in the loop. Required with --input; "
             "defaults to the preset's value with --preset.",
    )


def load_source(preset: str | None, input_path: str | None, measures: int | None,
                ) -> tuple[SourceAudio, int]:
    """Decode the preset or WAV named on the command line and resolve its measure count."""
    if input_path:
        if measures is None:
            raise CliError("--measures is required with --input")
        if not os.path.isfile(input_path):
            raise CliError(f"input file not found: {input_path}")
        wav_path = os.path.abspath(input_path)
    else:
        info = config.get_preset_info(preset)
        if not info:
            raise CliError(f"preset '{preset}' not found")
        wav_path = info["filepath"]
        if not os.path.isabs(wav_path):
            wav_path = str(PROJECT_ROOT / wav_path)
        if measures is None:
            measures = info.get("measures")
        if measures is None:
            raise CliError(f"preset '{preset}' has no measures; pass --measures")
    if measures < 1:
        raise CliError("--measures must be positive")
    try:
        audio = load_source_audio(wav_path)
    except (OSError, ValueError) as exc:
        raise CliError(str(exc)) from exc
    return audio, measures


def ms_to_samples(ms: float, sample_rate: int) -> int:
    return round(ms * sample_rate / 1000.0)
