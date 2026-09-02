"""SFZ writers: files dialect unchanged, offsets dialect matches the bundled presets."""

import os
import pathlib

import numpy as np
import pytest
import soundfile as sf

from export_utils import export_kit
from kit_manifest import KitManifest, Slice, build_manifest, load_source_audio
from sfz_writers import parse_sfz_offsets, write_sfz, write_sfz_files, write_sfz_offsets

ROOT = pathlib.Path(__file__).parent.parent
PRESET_DIR = ROOT / "presets" / "amen_classic"

SLICES = [
    Slice(1, 0, 22050, 60, "001.wav"),
    Slice(2, 22050, 44100, 61, "002.wav", "snare"),
    Slice(3, 44100, 66150, 62, "003.wav"),
]


def region_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("<region>")]


class TestFilesDialect:
    def test_regions_reference_slice_files_with_role_comments(self):
        assert write_sfz_files(SLICES) == (
            "<region> sample=001.wav key=60\n"
            "<region> sample=002.wav key=61 // snare\n"
            "<region> sample=003.wav key=62"
        )

    def test_ignores_offsets(self):
        assert "start=" not in write_sfz_files(SLICES)


class TestOffsetsDialect:
    def test_end_is_inclusive_and_role_is_a_comment(self):
        assert write_sfz_offsets("loop.wav", SLICES) == (
            "<region> sample=loop.wav start=0 end=22049 key=60\n"
            "<region> sample=loop.wav start=22050 end=44099 key=61 // snare\n"
            "<region> sample=loop.wav start=44100 end=66149 key=62"
        )

    @pytest.mark.parametrize("name", ["bukem.sfz", "dillinja.sfz"])
    def test_preset_round_trips_line_for_line(self, name):
        text = (PRESET_DIR / name).read_text()
        source, slices = parse_sfz_offsets(text)
        assert source == "amen.wav"
        assert region_lines(write_sfz_offsets(source, slices)) == region_lines(text)

    def test_parsed_preset_is_a_valid_manifest(self):
        info = sf.info(str(PRESET_DIR / "amen.wav"))
        source, slices = parse_sfz_offsets((PRESET_DIR / "bukem.sfz").read_text())
        boundaries = sorted({p for s in slices for p in (s.start, s.end)})
        manifest = KitManifest(
            source=source,
            sample_rate=info.samplerate,
            channels=info.channels,
            bpm=136.0,
            measures=4,
            region=(boundaries[0], boundaries[-1]),
            boundaries=boundaries,
            slices=slices,
        )
        manifest.validate()
        assert manifest.slices[0].role == "Clean kick"
        assert manifest.slices[0].key == 36

    def test_parse_rejects_other_lines(self):
        with pytest.raises(ValueError, match="line 1"):
            parse_sfz_offsets("<region> sample=001.wav key=60")

    def test_parse_rejects_mixed_sources(self):
        text = (
            "<region> sample=a.wav start=0 end=9 key=60\n"
            "<region> sample=b.wav start=10 end=19 key=61"
        )
        with pytest.raises(ValueError, match="differs"):
            parse_sfz_offsets(text)

    def test_parse_rejects_empty(self):
        with pytest.raises(ValueError, match="no <region>"):
            parse_sfz_offsets("// only a comment\n")


class TestDispatch:
    def test_unknown_dialect_raises(self):
        with pytest.raises(ValueError, match="unknown SFZ dialect"):
            write_sfz("bogus", "loop.wav", SLICES)

    def test_export_kit_writes_offsets_against_relative_source(self, tmp_path):
        wav = tmp_path / "src" / "loop.wav"
        wav.parent.mkdir()
        n = 2 * 44100
        sf.write(str(wav), np.zeros((n, 2)), 44100)
        audio = load_source_audio(str(wav))
        out = tmp_path / "kit"
        out.mkdir()
        stats = export_kit(build_manifest(audio, 1, 4), audio, str(out), sfz_dialect="offsets")
        lines = region_lines(pathlib.Path(stats["sfz_path"]).read_text())
        assert lines[0] == "<region> sample=../src/loop.wav start=0 end=22049 key=60"
        assert len(lines) == 4
        assert os.path.isfile(stats["manifest_path"])
        assert KitManifest.load(stats["manifest_path"]).source == "../src/loop.wav"
