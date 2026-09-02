"""Onset detection: the pure detector, the TUI path through it, and rcy-onsets."""

import json
import pathlib

import numpy as np
import pytest

from audio_processor import WavAudioProcessor
from kit_manifest import load_source_audio
from onsets import detect_onsets, detect_onsets_precise, nearest_onset
from utils.onsets_cli import main as onsets_main

ROOT = pathlib.Path(__file__).parent.parent
AMEN = ROOT / "presets" / "amen_classic" / "amen.wav"
SAMPLE_RATE = 44100


def clicks(positions: list[int], length: int) -> np.ndarray:
    """Silence with a short decaying burst of noise at each position."""
    rng = np.random.default_rng(0)
    signal = np.zeros(length, dtype=np.float32)
    burst = rng.standard_normal(2000).astype(np.float32) * np.exp(-np.arange(2000) / 400)
    for p in positions:
        signal[p : p + 2000] += burst
    return signal


class TestDetector:
    def test_finds_bursts_near_their_attacks(self):
        positions = [4410, 30000, 61000, 99000]
        onsets = detect_onsets_precise(clicks(positions, 132300), SAMPLE_RATE)
        assert len(onsets) == len(positions)
        for found, expected in zip(onsets, positions, strict=True):
            assert abs(found - expected) < 0.005 * SAMPLE_RATE  # within 5 ms

    def test_empty_signal_has_no_onsets(self):
        assert detect_onsets_precise(np.zeros(0, dtype=np.float32), SAMPLE_RATE) == []

    def test_silence_has_no_onsets(self):
        assert detect_onsets_precise(np.zeros(44100, dtype=np.float32), SAMPLE_RATE) == []

    def test_results_are_ascending_ints_inside_the_signal(self):
        audio = load_source_audio(str(AMEN))
        onsets = detect_onsets_precise(audio.data_left, audio.sample_rate)
        assert len(onsets) > 30
        assert all(isinstance(o, int) for o in onsets)
        assert onsets == sorted(onsets) and onsets[0] >= 0 and onsets[-1] < audio.total_samples

    def test_frame_level_parameters_are_the_tui_path(self):
        signal = clicks([4410, 30000, 61000], 88200)
        onsets = detect_onsets(
            signal, SAMPLE_RATE, delta=0.02, wait=1, pre_max=1, post_max=1
        )
        assert len(onsets) == 3
        assert all(o % 512 == 0 for o in onsets)

    def test_nearest_onset(self):
        assert nearest_onset(100, [10, 90, 300]) == 90
        assert nearest_onset(100, []) is None
        assert nearest_onset(50, [40, 60]) == 40  # ties go to the earlier onset


class TestTuiSplitUsesTheDetector:
    def test_split_by_transients_matches_detect_onsets(self):
        model = WavAudioProcessor(preset_id="amen_classic")
        boundaries = model.split_by_transients(threshold=0.2)
        expected = detect_onsets(
            model.data_left, model.sample_rate, delta=0.02, wait=1, pre_max=1, post_max=1
        )
        assert boundaries[0] == 0 and boundaries[-1] == len(model.data_left)
        # the TUI path goes through seconds and truncates, so allow one sample
        assert len(boundaries) - 2 == len(expected)
        assert all(abs(a - b) <= 1 for a, b in zip(boundaries[1:-1], expected, strict=True))


class TestOnsetsCli:
    def test_prints_a_table_with_beat_positions(self, capsys):
        assert onsets_main(["--preset", "amen_classic"]) == 0
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[1].startswith("tempo: 137.72 BPM, 4 measures")
        assert lines[2].startswith("onsets: ")
        assert lines[3].split() == ["#", "sample", "seconds", "beat", "grid_ms"]
        first = lines[4].split()
        assert first[0] == "1" and first[3] == "1.1.1"

    def test_json_lists_every_onset(self, capsys):
        assert onsets_main(["--preset", "amen_classic", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["measures"] == 4
        assert data["bpm"] == pytest.approx(137.72, abs=0.01)
        audio = load_source_audio(str(AMEN))
        expected = detect_onsets_precise(audio.data_left, audio.sample_rate)
        assert [o["sample"] for o in data["onsets"]] == expected
        assert {"index", "sample", "seconds", "beat", "grid_ms"} <= data["onsets"][0].keys()

    def test_input_needs_measures(self, capsys):
        assert onsets_main(["--input", str(AMEN)]) == 2
        assert "--measures" in capsys.readouterr().err

    def test_missing_preset_is_an_error(self, capsys):
        assert onsets_main(["--preset", "nope"]) == 2
        assert "not found" in capsys.readouterr().err

    def test_grid_offset_moves_beat_positions(self, capsys):
        onsets_main(["--preset", "amen_classic", "--json"])
        plain = json.loads(capsys.readouterr().out)
        onsets_main(["--preset", "amen_classic", "--json", "--grid-offset", "20"])
        shifted = json.loads(capsys.readouterr().out)
        assert shifted["grid_offset"] == 882
        # every onset sits 20 ms earlier relative to the shifted grid
        for a, b in zip(plain["onsets"], shifted["onsets"], strict=True):
            assert b["sample"] == a["sample"]
            if a["beat"] == b["beat"]:
                assert b["grid_ms"] == pytest.approx(a["grid_ms"] - 20.0, abs=0.1)
