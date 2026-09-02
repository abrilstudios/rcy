"""Beat grid: beat positions to samples and back."""

import pytest

from beat_grid import BeatGrid, label_for_sixteenth

# 120 BPM at 44.1 kHz: one beat is 22050 samples, one sixteenth 5512.5.
GRID = BeatGrid(sample_rate=44100, bpm=120.0)


class TestPositions:
    def test_first_sixteenth_is_the_grid_offset(self):
        assert GRID.sample_at(1, 1, 1) == 0
        assert BeatGrid(44100, 120.0, offset=100).sample_at(1, 1) == 100

    def test_bar_beat_sixteenth_to_sample(self):
        assert GRID.sample_at(1, 2) == 22050
        assert GRID.sample_at(1, 1, 3) == 11025
        assert GRID.sample_at(2, 1) == 88200
        assert GRID.sample_at(2, 3, 4) == 88200 + 2 * 22050 + round(3 * 5512.5)

    @pytest.mark.parametrize("bar, beat, sixteenth", [(0, 1, 1), (1, 0, 1), (1, 5, 1), (1, 1, 5)])
    def test_out_of_range_positions_raise(self, bar, beat, sixteenth):
        with pytest.raises(ValueError):
            GRID.sample_at(bar, beat, sixteenth)

    def test_label_of_nearest_sixteenth(self):
        assert GRID.label(0) == "1.1.1"
        assert GRID.label(22050) == "1.2.1"
        assert GRID.label(22050 + 2000) == "1.2.1"
        assert GRID.label(22050 + 3000) == "1.2.2"
        assert GRID.label(88200 * 3) == "4.1.1"

    def test_distance_to_nearest_sixteenth_is_signed_ms(self):
        assert GRID.distance_to_sixteenth_ms(22050 + 441) == pytest.approx(10.0)
        assert GRID.distance_to_sixteenth_ms(22050 - 441) == pytest.approx(-10.0)

    def test_sixteenths_length(self):
        assert GRID.sixteenths(22050) == pytest.approx(4.0)

    @pytest.mark.parametrize(
        "index, label", [(0, "1.1.1"), (1, "1.1.2"), (4, "1.2.1"), (15, "1.4.4"), (16, "2.1.1")]
    )
    def test_label_for_sixteenth(self, index, label):
        assert label_for_sixteenth(index) == label


class TestParsePosition:
    @pytest.mark.parametrize(
        "text, sample",
        [
            ("19388", 19388),
            ("0", 0),
            ("0.5s", 22050),
            ("1s", 44100),
            (".25s", 11025),
            ("1.1", 0),
            ("1.2", 22050),
            ("1.2.3", 22050 + 11025),
            ("2.1.1", 88200),
            (" 2.1 ", 88200),
        ],
    )
    def test_samples_seconds_and_beats(self, text, sample):
        assert GRID.parse_position(text) == sample

    @pytest.mark.parametrize("text", ["", "abc", "1.5", "2.3.5", "-5", "1.2.3.4", "0.5", "1,2"])
    def test_rejects_other_forms(self, text):
        with pytest.raises(ValueError):
            GRID.parse_position(text)

    def test_grid_offset_shifts_beats_not_samples(self):
        grid = BeatGrid(44100, 120.0, offset=441)
        assert grid.parse_position("1.1") == 441
        assert grid.parse_position("1.2") == 22050 + 441
        assert grid.parse_position("22050") == 22050
        assert grid.parse_position("0.5s") == 22050
