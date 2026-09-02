"""Cut lists, onset snapping, roles in every output, and the per-slice table."""

import io
import json
import os
import pathlib

import mido
import pytest

from beat_grid import BeatGrid
from cut_list import (
    Cut,
    boundaries_from_cuts,
    format_table,
    parse_cut_list,
    slice_rows,
    snap_to_onsets,
)
from kit_manifest import KitManifest, manifest_path_for
from utils.export_cli import main as export_main

ROOT = pathlib.Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
FIXTURE_MANIFEST = FIXTURES / "amen_classic_chops.rcy.json"
FIXTURE_CUTS = FIXTURES / "amen_classic_chops.cuts"
SAMPLE_RATE = 44100
GRID = BeatGrid(SAMPLE_RATE, 120.0)  # one sixteenth is 5512.5 samples


def export(tmp_path: pathlib.Path, *args: str, name: str = "kit") -> tuple[int, KitManifest]:
    out = tmp_path / name
    code = export_main([*args, "--out", str(out)])
    manifest = KitManifest.load(manifest_path_for(str(out))) if code == 0 else None
    return code, manifest


class TestParseCutList:
    def test_positions_roles_comments_and_blank_lines(self):
        text = "# header\n\n0 kick\n1.2   snare cell\n0.75s\n33075 hat two words\n"
        assert parse_cut_list(text, GRID) == [
            Cut(0, "kick"),
            Cut(22050, "snare cell"),
            Cut(33075, ""),
            Cut(33075, "hat two words"),
        ]

    def test_bad_position_names_the_line(self):
        with pytest.raises(ValueError, match="cuts line 2"):
            parse_cut_list("0 kick\nbeat two snare\n", GRID)

    def test_empty_list_is_an_error(self):
        with pytest.raises(ValueError, match="no cuts"):
            parse_cut_list("# nothing here\n", GRID)


class TestBoundariesFromCuts:
    def test_first_cut_at_zero_is_implied(self):
        boundaries, roles = boundaries_from_cuts([Cut(100, "a"), Cut(200, "b")], 300)
        assert boundaries == [0, 100, 200, 300]
        assert roles == ["", "a", "b"]

    def test_explicit_first_cut_keeps_its_role(self):
        boundaries, roles = boundaries_from_cuts([Cut(0, "a"), Cut(200, "b")], 300)
        assert boundaries == [0, 200, 300]
        assert roles == ["a", "b"]

    def test_cuts_must_increase(self):
        with pytest.raises(ValueError, match="increase"):
            boundaries_from_cuts([Cut(200), Cut(100)], 300)

    def test_cut_past_the_end_is_an_error(self):
        with pytest.raises(ValueError, match="end of the file"):
            boundaries_from_cuts([Cut(300)], 300)


class TestSnapToOnsets:
    def test_moves_cuts_to_before_the_nearest_onset(self):
        boundaries = [0, 22050, 44100, 88200]
        onsets = [500, 22500, 44000]
        snapped, warnings = snap_to_onsets(boundaries, onsets, GRID, pre_ms=3.0)
        assert snapped == [0, 22500 - 132, 44000 - 132, 88200]
        assert warnings == []

    def test_leaves_cuts_with_no_nearby_onset_and_warns(self):
        boundaries = [0, 22050, 44100, 88200]
        snapped, warnings = snap_to_onsets(boundaries, [500, 44000], GRID, pre_ms=3.0)
        assert snapped == [0, 22050, 44000 - 132, 88200]
        assert len(warnings) == 1 and "22050" in warnings[0] and "1.2.1" in warnings[0]

    def test_window_is_half_a_sixteenth(self):
        just_inside = 22050 + 2756
        just_outside = 22050 + 2757
        assert snap_to_onsets([0, 22050, 88200], [just_inside], GRID, 0.0)[0][1] == just_inside
        assert snap_to_onsets([0, 22050, 88200], [just_outside], GRID, 0.0)[0][1] == 22050

    def test_crossing_cuts_raise(self):
        with pytest.raises(ValueError, match="cross"):
            snap_to_onsets([0, 1000, 1100, 88200], [1200], GRID, 3.0)


class TestSliceTable:
    def test_rows_carry_beat_lengths_and_onset_distance(self):
        manifest = KitManifest.load(str(FIXTURE_MANIFEST))
        manifest = KitManifest(**{**manifest.__dict__, "onsets": [512, 19520]})
        rows = slice_rows(manifest)
        assert rows[0]["beat"] == "1.1.1" and rows[0]["onset_ms"] == pytest.approx(11.6)
        assert rows[1]["beat"] == "1.2.1" and rows[1]["onset_ms"] == pytest.approx(3.0)
        assert rows[1]["length_sixteenths"] == pytest.approx(6.02)
        assert rows[2]["beat"] == "1.3.3" and rows[2]["role"] == "b1 turnaround"
        assert rows[2]["onset_ms"] == pytest.approx((19520 - 48316) / 44.1, abs=0.1)

    def test_format_table_aligns_columns_and_blanks_none(self):
        rows = [{"a": 1, "b": None}, {"a": 100, "b": "x"}]
        text = format_table(rows, [("a", "A"), ("b", "B")])
        assert text == "A    B\n1\n100  x"


class TestExportWithCuts:
    def test_reproduces_the_owner_approved_amen_chop(self, tmp_path):
        code, manifest = export(
            tmp_path, "--preset", "amen_classic", "--cuts", str(FIXTURE_CUTS),
            "--snap-onsets", "3",
        )
        assert code == 0
        fixture = KitManifest.load(str(FIXTURE_MANIFEST))
        tolerance = round(0.002 * SAMPLE_RATE)
        for ours, theirs in zip(manifest.boundaries, fixture.boundaries, strict=True):
            assert abs(ours - theirs) <= tolerance
        assert [s.role for s in manifest.slices] == [s.role for s in fixture.slices]
        assert [s.key for s in manifest.slices] == [s.key for s in fixture.slices]
        assert manifest.onsets and manifest.onsets == sorted(manifest.onsets)

    def test_cuts_in_samples_and_seconds_without_snapping(self, tmp_path):
        cuts = tmp_path / "cuts.txt"
        cuts.write_text("22050 first\n1.0s second\n2.1 third\n")
        code, manifest = export(tmp_path, "--preset", "amen_classic", "--cuts", str(cuts))
        assert code == 0
        assert manifest.boundaries[:4] == [0, 22050, 44100, 76853]
        assert [s.role for s in manifest.slices] == ["", "first", "second", "third"]
        assert manifest.onsets == []

    def test_cuts_from_stdin(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("1.2 snare\n"))
        code, manifest = export(tmp_path, "--preset", "amen_classic", "--cuts", "-")
        assert code == 0
        assert len(manifest.slices) == 2 and manifest.slices[1].role == "snare"

    def test_bad_cut_is_reported_with_its_line(self, tmp_path, capsys):
        cuts = tmp_path / "cuts.txt"
        cuts.write_text("1.2 ok\n9.9.9 bad\n")
        code, _ = export(tmp_path, "--preset", "amen_classic", "--cuts", str(cuts))
        assert code == 2
        assert "cuts line 2" in capsys.readouterr().err

    def test_cuts_and_resolution_are_exclusive(self, tmp_path):
        with pytest.raises(SystemExit):
            export(tmp_path, "--preset", "amen_classic", "--cuts", "x", "--resolution", "8")

    def test_snap_warns_for_cuts_without_an_onset(self, tmp_path, capsys):
        cuts = tmp_path / "cuts.txt"
        cuts.write_text("1.2 snare\n")
        # 2.5 s into the apache break is between hits at its resolution: force a miss by
        # cutting a silent synthetic file instead.
        import numpy as np
        import soundfile as sf
        wav = tmp_path / "silence.wav"
        sf.write(str(wav), np.zeros((88200, 2)), SAMPLE_RATE)
        code, manifest = export(
            tmp_path, "--input", str(wav), "--measures", "1", "--cuts", str(cuts),
            "--snap-onsets",
        )
        assert code == 0
        assert manifest.boundaries == [0, 22050, 88200]
        assert "warning: cut at 22050 (1.2.1)" in capsys.readouterr().err


class TestEqualChopsWithGridAndSnap:
    def test_grid_offset_shifts_interior_cuts(self, tmp_path):
        _, plain = export(tmp_path, "--preset", "apache_break", name="plain")
        _, shifted = export(
            tmp_path, "--preset", "apache_break", "--grid-offset", "10", name="shifted"
        )
        assert shifted.grid_offset == 441
        assert shifted.boundaries[0] == 0 and shifted.boundaries[-1] == plain.boundaries[-1]
        assert shifted.boundaries[1:-1] == [b + 441 for b in plain.boundaries[1:-1]]

    def test_snap_applies_to_equal_chops(self, tmp_path):
        code, manifest = export(
            tmp_path, "--preset", "amen_classic", "--resolution", "4", "--snap-onsets",
        )
        assert code == 0
        assert len(manifest.slices) == 16
        assert manifest.boundaries[1] == 19388  # bar 1 beat 2, the snare
        assert manifest.boundaries[4] == 77564  # bar 2 downbeat

    def test_onsets_flag_records_onsets_without_moving_cuts(self, tmp_path):
        _, plain = export(tmp_path, "--preset", "amen_classic", name="plain")
        _, with_onsets = export(
            tmp_path, "--preset", "amen_classic", "--onsets", name="onsets"
        )
        assert with_onsets.boundaries == plain.boundaries
        assert plain.onsets == [] and len(with_onsets.onsets) > 30
        data = json.loads(pathlib.Path(manifest_path_for(str(tmp_path / "onsets"))).read_text())
        assert data["onsets"] == with_onsets.onsets
        assert "onsets" not in json.loads(
            pathlib.Path(manifest_path_for(str(tmp_path / "plain"))).read_text()
        )

    def test_from_manifest_can_snap_using_recorded_onsets(self, tmp_path):
        _, manifest = export(tmp_path, "--preset", "amen_classic", "--onsets")
        path = manifest_path_for(str(tmp_path / "kit"))
        assert export_main(["--from-manifest", path, "--snap-onsets"]) == 0
        snapped = KitManifest.load(path)
        assert snapped.boundaries[1] == 19388
        assert snapped.onsets == manifest.onsets

    def test_from_manifest_rejects_cut_options(self, tmp_path, capsys):
        export(tmp_path, "--preset", "apache_break")
        path = manifest_path_for(str(tmp_path / "kit"))
        assert export_main(["--from-manifest", path, "--cuts", "x"]) == 2
        assert "--cuts" in capsys.readouterr().err


class TestReporting:
    def test_table_lists_every_slice(self, tmp_path, capsys):
        export(tmp_path, "--preset", "amen_classic", "--cuts", str(FIXTURE_CUTS), "--snap-onsets")
        out = capsys.readouterr().out.splitlines()
        assert out[1] == "tempo: 137.72 BPM, 4 measures"
        assert out[2] == "slices: 12"
        assert out[3].startswith("onsets: ")
        header = next(line for line in out if line.startswith("#"))
        assert header.split() == ["#", "key", "role", "start", "beat", "grid_ms", "16ths",
                                  "onset_ms"]
        rows = out[out.index(header) + 1:]
        assert len(rows) == 12
        assert rows[1].split()[:2] == ["2", "61"]
        assert "b1 snare cell" in rows[1] and "1.2.1" in rows[1]

    def test_equal_chop_reports_resolution(self, tmp_path, capsys):
        export(tmp_path, "--preset", "apache_break")
        out = capsys.readouterr().out.splitlines()
        assert out[2] == "slices: 8, 4 per measure"
        assert "onsets:" not in "\n".join(out)
        header = next(line for line in out if line.startswith("#"))
        assert "onset_ms" not in header

    def test_uneven_manifest_reports_no_resolution(self, tmp_path, capsys):
        cuts = tmp_path / "cuts.txt"
        cuts.write_text("1.2\n1.3\n1.4\n2.1\n2.3\n2.4\n3.1\n")
        export(tmp_path, "--preset", "amen_classic", "--cuts", str(cuts))
        assert capsys.readouterr().out.splitlines()[2] == "slices: 8"

    def test_json_output(self, tmp_path, capsys):
        _, manifest = export(
            tmp_path, "--preset", "amen_classic", "--cuts", str(FIXTURE_CUTS),
            "--snap-onsets", "--json",
        )
        data = json.loads(capsys.readouterr().out)
        assert data["slice_count"] == 12 and data["resolution"] is None
        assert data["measures"] == 4 and data["onset_count"] == len(manifest.onsets)
        assert data["slices"] == slice_rows(manifest)
        assert data["slices"][2]["role"] == "b1 turnaround"
        assert data["sfz"].endswith("kit.sfz") and data["rendered"] is True


class TestRolesEverywhere:
    def test_files_sfz_carries_roles(self, tmp_path):
        export(tmp_path, "--preset", "amen_classic", "--cuts", str(FIXTURE_CUTS))
        lines = (tmp_path / "kit" / "kit.sfz").read_text().splitlines()
        assert lines[1] == "<region> sample=002.wav key=61 // b1 snare cell"
        assert lines[0] == "<region> sample=001.wav key=60 // b1 kicks"

    def test_midi_carries_roles_as_text_events(self, tmp_path):
        export(tmp_path, "--preset", "amen_classic", "--cuts", str(FIXTURE_CUTS))
        midi = mido.MidiFile(str(tmp_path / "kit" / "kit.mid"))
        events = [m for track in midi.tracks for m in track]
        texts = [m.text for m in events if m.type == "text"]
        assert texts == [s.role for s in KitManifest.load(str(FIXTURE_MANIFEST)).slices]
        # each text sits at the same tick as its note
        tick = 0
        text_ticks, note_ticks = [], []
        for m in midi.tracks[0]:
            tick += m.time
            if m.type == "text":
                text_ticks.append(tick)
            if m.type == "note_on" and m.velocity > 0:
                note_ticks.append(tick)
        assert text_ticks == note_ticks

    def test_offsets_dialect_skips_slice_wavs_unless_render(self, tmp_path, capsys):
        code, _ = export(
            tmp_path, "--preset", "apache_break", "--sfz-dialect", "offsets", name="offsets"
        )
        assert code == 0
        names = sorted(os.listdir(tmp_path / "offsets"))
        assert names == ["offsets.mid", "offsets.rcy.json", "offsets.sfz"]
        assert "slice WAVs not written" in capsys.readouterr().out
        code, _ = export(
            tmp_path, "--preset", "apache_break", "--sfz-dialect", "offsets", "--render",
            name="rendered",
        )
        assert (tmp_path / "rendered" / "001.wav").is_file()


class TestHeadlessLogging:
    def test_export_writes_no_logs_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        code, _ = export(tmp_path, "--preset", "apache_break")
        assert code == 0
        assert not (tmp_path / "logs").exists()
