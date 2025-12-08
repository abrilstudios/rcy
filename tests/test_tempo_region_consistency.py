"""
Tests for tempo calculation consistency with L/R region markers.
Verifies fix for issue #158.

Run with: PYTHONPATH=src/python pytest tests/test_tempo_region_consistency.py -v
"""

import pytest
from audio_processor import WavAudioProcessor


class TestTempoRegionConsistency:
    """Test that tempo calculation uses L/R region, not full file."""

    @pytest.fixture
    def processor(self):
        """Create processor with amen_classic preset (4 bars)."""
        return WavAudioProcessor(preset_id='amen_classic')

    def test_full_file_bpm_calculation(self, processor):
        """Baseline: BPM calculation for full file."""
        full_duration = processor.total_time
        measures = 4
        beats = measures * 4
        expected_bpm = (60.0 * beats) / full_duration

        actual_bpm = processor.calculate_source_bpm(measures=measures)

        assert abs(actual_bpm - expected_bpm) < 0.1, \
            f"Full file BPM: expected {expected_bpm:.2f}, got {actual_bpm:.2f}"

    def test_region_bpm_calculation_half_file(self, processor):
        """BPM calculation for half the file should be 2x faster."""
        full_duration = processor.total_time
        half_duration = full_duration / 2

        # If full file is 4 bars at ~138 BPM, half file with 2 bars should still be ~138 BPM
        # But if we say half file is 4 bars, it should be ~276 BPM

        # Calculate with region = first half, 2 measures (should match full file BPM)
        bpm_2_bars_half = processor.calculate_source_bpm(
            measures=2,
            start_time=0.0,
            end_time=half_duration
        )

        # Should be approximately same as full file with 4 bars
        full_bpm = processor.calculate_source_bpm(measures=4)

        assert abs(bpm_2_bars_half - full_bpm) < 1.0, \
            f"2 bars in half file ({bpm_2_bars_half:.2f}) should match 4 bars in full file ({full_bpm:.2f})"

    def test_region_bpm_changes_with_measure_count(self, processor):
        """Changing measure count should use region duration, not full file."""
        full_duration = processor.total_time
        region_start = full_duration * 0.25  # Start at 25%
        region_end = full_duration * 0.75    # End at 75%
        region_duration = region_end - region_start  # 50% of file

        # Calculate BPM for 1 measure in this region
        bpm_1_measure = processor.calculate_source_bpm(
            measures=1,
            start_time=region_start,
            end_time=region_end
        )
        expected_1 = (60.0 * 4) / region_duration

        # Calculate BPM for 2 measures in same region
        bpm_2_measures = processor.calculate_source_bpm(
            measures=2,
            start_time=region_start,
            end_time=region_end
        )
        expected_2 = (60.0 * 8) / region_duration

        assert abs(bpm_1_measure - expected_1) < 0.1, \
            f"1 measure: expected {expected_1:.2f}, got {bpm_1_measure:.2f}"
        assert abs(bpm_2_measures - expected_2) < 0.1, \
            f"2 measures: expected {expected_2:.2f}, got {bpm_2_measures:.2f}"

        # 2 measures should be exactly 2x the BPM of 1 measure
        assert abs(bpm_2_measures - 2 * bpm_1_measure) < 0.1, \
            f"2 measures BPM ({bpm_2_measures:.2f}) should be 2x 1 measure ({bpm_1_measure:.2f})"

    def test_region_bpm_ignores_file_outside_region(self, processor):
        """BPM should only depend on region, not parts of file outside it."""
        full_duration = processor.total_time

        # Two different regions of same duration
        region1_start = 0.0
        region1_end = full_duration / 2

        region2_start = full_duration / 2
        region2_end = full_duration

        # Both with same measure count should give same BPM
        bpm_region1 = processor.calculate_source_bpm(
            measures=2,
            start_time=region1_start,
            end_time=region1_end
        )

        bpm_region2 = processor.calculate_source_bpm(
            measures=2,
            start_time=region2_start,
            end_time=region2_end
        )

        assert abs(bpm_region1 - bpm_region2) < 0.1, \
            f"Same duration regions should have same BPM: {bpm_region1:.2f} vs {bpm_region2:.2f}"

    def test_small_region_high_bpm(self, processor):
        """Small region with 1 measure should calculate high BPM correctly."""
        full_duration = processor.total_time

        # Very small region (1/8 of file)
        region_start = 0.0
        region_end = full_duration / 8
        region_duration = region_end - region_start

        # 1 measure in this small region
        bpm = processor.calculate_source_bpm(
            measures=1,
            start_time=region_start,
            end_time=region_end
        )

        expected_bpm = (60.0 * 4) / region_duration

        assert abs(bpm - expected_bpm) < 0.1, \
            f"Small region BPM: expected {expected_bpm:.2f}, got {bpm:.2f}"

        # Should be much higher than full file BPM
        full_bpm = processor.calculate_source_bpm(measures=4)
        assert bpm > full_bpm * 1.5, \
            f"Small region BPM ({bpm:.2f}) should be much higher than full file ({full_bpm:.2f})"
