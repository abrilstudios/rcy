"""Kit manifest: save/load round trip, validation, headless loading and re-export."""

import hashlib
import json
import os
import pathlib

import numpy as np
import pytest
import soundfile as sf

from kit_manifest import (
    KitManifest,
    ManifestError,
    Slice,
    build_manifest,
    load_kit,
    load_source_audio,
    manifest_path_for,
    measure_boundaries,
)
from segment_manager import SegmentManager
from utils.export_cli import main as export_main

ROOT = pathlib.Path(__file__).parent.parent
SAMPLE_RATE = 44100


def write_wav(path: pathlib.Path, seconds: float = 2.0, channels: int = 2) -> pathlib.Path:
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    left = 0.5 * np.sin(2 * np.pi * 220 * t)
    data = np.column_stack([left, 0.25 * left]) if channels == 2 else left
    sf.write(str(path), data, SAMPLE_RATE)
    return path


def example_manifest(source: str = "loop.wav") -> KitManifest:
    boundaries = [0, 22050, 44100, 66150, 88200]
    return KitManifest(
        source=source,
        sample_rate=SAMPLE_RATE,
        channels=2,
        bpm=120.0,
        measures=1,
        region=(0, 88200),
        boundaries=boundaries,
        slices=[
            Slice(1, 0, 22050, 60, "001.wav", "kick"),
            Slice(2, 22050, 44100, 61, "002.wav"),
            Slice(3, 44100, 66150, 62, "003.wav"),
            Slice(4, 66150, 88200, 63, "004.wav", "snare"),
        ],
    )


def wav_digests(directory: str) -> dict[str, str]:
    out = {}
    for name in sorted(os.listdir(directory)):
        if name.endswith(".wav"):
            out[name] = hashlib.sha256(pathlib.Path(directory, name).read_bytes()).hexdigest()
    return out


class TestRoundTrip:
    def test_save_then_load_is_equal(self, tmp_path):
        manifest = example_manifest()
        path = tmp_path / "loop.rcy.json"
        manifest.save(str(path))
        assert KitManifest.load(str(path)) == manifest

    def test_saved_json_shape(self, tmp_path):
        path = tmp_path / "loop.rcy.json"
        example_manifest().save(str(path))
        data = json.loads(path.read_text())
        assert data["rcy"] == 1
        assert data["region"] == {"start": 0, "end": 88200}
        assert data["slices"][0] == {
            "index": 1, "start": 0, "end": 22050, "key": 60, "file": "001.wav", "role": "kick",
        }
        assert data["slices"][1]["role"] == ""

    def test_source_path_resolves_relative_to_manifest(self, tmp_path):
        manifest = example_manifest("../src/loop.wav")
        path = tmp_path / "kit" / "kit.rcy.json"
        assert manifest.source_path(str(path)) == str(tmp_path / "src" / "loop.wav")

    def test_rebased_uses_relative_path_inside_a_shared_tree(self, tmp_path):
        source = str(tmp_path / "src" / "loop.wav")
        manifest = example_manifest().rebased(source, str(tmp_path / "out"))
        assert manifest.source == "../src/loop.wav"


class TestValidation:
    @pytest.mark.parametrize(
        "mutate, message",
        [
            (lambda d: d.update(rcy=2), "version"),
            (lambda d: d.update(sample_rate="44100"), "sample_rate"),
            (lambda d: d.update(channels=3), "channels"),
            (lambda d: d.update(bpm=0), "bpm"),
            (lambda d: d.update(measures=0), "measures"),
            (lambda d: d.update(region=[0, 88200]), "region"),
            (lambda d: d.update(region={"start": 0}), "end must be an integer"),
            (lambda d: d.update(boundaries=[0, 44100, 22050, 66150, 88200]), "increasing"),
            (lambda d: d.update(boundaries=[0, 22050, 44100, 66150]), "region end"),
            (lambda d: d["slices"][2].update(index=5), "sequential"),
            (lambda d: d["slices"][3].update(end=99999), "outside"),
            (lambda d: d["slices"][1].update(start=30000), "boundaries"),
            (lambda d: d["slices"][0].update(key=128), "MIDI note"),
            (lambda d: d["slices"][0].update(file=""), "file"),
            (lambda d: d["slices"][1].update(file="001.wav"), "more than one"),
            (lambda d: d["slices"][0].update(role=3), "role"),
            (lambda d: d["slices"][0].update(start=True), "integer"),
            (lambda d: d.update(slices=[]), "slices"),
        ],
    )
    def test_malformed_manifest_raises(self, mutate, message):
        data = example_manifest().to_dict()
        mutate(data)
        with pytest.raises(ManifestError, match=message):
            KitManifest.from_dict(data)

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.rcy.json"
        path.write_text("{not json")
        with pytest.raises(ManifestError, match="invalid JSON"):
            KitManifest.load(str(path))

    def test_non_object_raises(self):
        with pytest.raises(ManifestError, match="JSON object"):
            KitManifest.from_dict([1, 2, 3])

    def test_load_kit_rejects_channel_mismatch(self, tmp_path):
        write_wav(tmp_path / "loop.wav", channels=1)
        path = tmp_path / "loop.rcy.json"
        example_manifest().save(str(path))
        with pytest.raises(ManifestError, match="channels"):
            load_kit(str(path))

    def test_load_kit_rejects_region_past_end_of_file(self, tmp_path):
        write_wav(tmp_path / "loop.wav", seconds=1.0)
        path = tmp_path / "loop.rcy.json"
        example_manifest().save(str(path))
        with pytest.raises(ManifestError, match="exceeds source length"):
            load_kit(str(path))


class TestHeadlessLoading:
    def test_load_source_audio_reads_stereo(self, tmp_path):
        audio = load_source_audio(str(write_wav(tmp_path / "loop.wav")))
        assert audio.channels == 2 and audio.is_stereo
        assert audio.total_samples == 2 * SAMPLE_RATE
        assert not np.array_equal(audio.data_left, audio.data_right)

    def test_load_source_audio_duplicates_mono(self, tmp_path):
        audio = load_source_audio(str(write_wav(tmp_path / "loop.wav", channels=1)))
        assert audio.channels == 1
        assert np.array_equal(audio.data_left, audio.data_right)

    def test_load_source_audio_rejects_other_rates(self, tmp_path):
        path = tmp_path / "48k.wav"
        sf.write(str(path), np.zeros(4800), 48000)
        with pytest.raises(ValueError, match="44100"):
            load_source_audio(str(path))

    def test_load_kit_returns_manifest_and_audio(self, tmp_path):
        write_wav(tmp_path / "loop.wav")
        path = tmp_path / "loop.rcy.json"
        example_manifest().save(str(path))
        manifest, audio = load_kit(str(path))
        assert [s.key for s in manifest.slices] == [60, 61, 62, 63]
        assert manifest.boundaries == [0, 22050, 44100, 66150, 88200]
        assert audio.path == str(tmp_path / "loop.wav")

    @pytest.mark.parametrize("measures, resolution", [(1, 4), (2, 4), (4, 8), (3, 3)])
    def test_measure_boundaries_match_segment_manager(self, measures, resolution):
        total_samples = 176400 + 7  # not divisible, exercises truncation
        manager = SegmentManager()
        manager.set_audio_context(total_samples, SAMPLE_RATE)
        manager.split_by_measures(measures, resolution, 0.0, total_samples / SAMPLE_RATE)
        ours = measure_boundaries(total_samples, SAMPLE_RATE, measures, resolution)
        assert ours == manager.get_boundaries()

    def test_build_manifest_from_preset_wav(self):
        audio = load_source_audio(str(ROOT / "presets" / "apache_break" / "apache.wav"))
        manifest = build_manifest(audio, measures=2, resolution=4)
        assert len(manifest.slices) == 8
        assert manifest.bpm == pytest.approx(120.0, abs=0.01)
        assert manifest.slices[0].key == 60 and manifest.slices[-1].key == 67
        assert manifest.slices[-1].end == audio.total_samples


class TestReExport:
    def test_from_manifest_reproduces_identical_wavs(self, tmp_path):
        out = tmp_path / "apache"
        assert export_main(["--preset", "apache_break", "--out", str(out)]) == 0
        manifest_path = manifest_path_for(str(out))
        assert os.path.isfile(manifest_path)
        first = wav_digests(str(out))
        assert len(first) == 8

        assert export_main(["--from-manifest", manifest_path]) == 0
        assert wav_digests(str(out)) == first

        elsewhere = tmp_path / "copy"
        assert export_main(["--from-manifest", manifest_path, "--out", str(elsewhere)]) == 0
        assert wav_digests(str(elsewhere)) == first
        copied = KitManifest.load(manifest_path_for(str(elsewhere)))
        assert copied.slices == KitManifest.load(manifest_path).slices

    def test_editing_a_boundary_moves_the_cut(self, tmp_path):
        out = tmp_path / "apache"
        export_main(["--preset", "apache_break", "--out", str(out)])
        manifest_path = manifest_path_for(str(out))
        data = json.loads(pathlib.Path(manifest_path).read_text())
        old = data["boundaries"][1]
        new = old + 1000
        data["boundaries"][1] = new
        data["slices"][0]["end"] = new
        data["slices"][1]["start"] = new
        pathlib.Path(manifest_path).write_text(json.dumps(data))

        assert export_main(["--from-manifest", manifest_path]) == 0
        assert sf.info(str(out / "001.wav")).frames == new
        assert sf.info(str(out / "002.wav")).frames == data["boundaries"][2] - new
        assert KitManifest.load(manifest_path).slices[0].end == new

    def test_inconsistent_edit_is_refused(self, tmp_path, capsys):
        out = tmp_path / "apache"
        export_main(["--preset", "apache_break", "--out", str(out)])
        manifest_path = manifest_path_for(str(out))
        data = json.loads(pathlib.Path(manifest_path).read_text())
        data["slices"][0]["end"] += 1000  # boundary and slice 2 left untouched
        pathlib.Path(manifest_path).write_text(json.dumps(data))
        assert export_main(["--from-manifest", manifest_path]) == 2
        assert "boundaries" in capsys.readouterr().err

    def test_input_wav_needs_no_preset(self, tmp_path):
        wav = write_wav(tmp_path / "loop.wav")
        out = tmp_path / "loop"
        assert export_main(["--input", str(wav), "--measures", "1", "--out", str(out)]) == 0
        manifest = KitManifest.load(manifest_path_for(str(out)))
        assert manifest.source == "../loop.wav"
        assert manifest.measures == 1 and len(manifest.slices) == 4
