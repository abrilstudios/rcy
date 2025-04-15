"""
Tests for the SFZ Generator utility.
"""

import os
import tempfile
import shutil
import pytest
from utils.sfz.generate_sfz import collect_audio_files, generate_sfz, is_audio_file


class TestSFZGenerator:
    """Test suite for SFZ Generator functionality."""

    @pytest.fixture
    def sample_dir(self):
        """Create a temporary directory with sample audio files."""
        temp_dir = tempfile.mkdtemp()
        
        # Create some dummy audio files
        os.makedirs(os.path.join(temp_dir, "kicks"))
        os.makedirs(os.path.join(temp_dir, "snares"))
        
        # Create dummy wav files
        open(os.path.join(temp_dir, "kicks", "kick1.wav"), 'w').close()
        open(os.path.join(temp_dir, "kicks", "kick2.wav"), 'w').close()
        open(os.path.join(temp_dir, "snares", "snare1.wav"), 'w').close()
        open(os.path.join(temp_dir, "snares", "snare2.wav"), 'w').close()
        
        # Create a non-audio file
        open(os.path.join(temp_dir, "readme.txt"), 'w').close()
        
        # Create a hidden file
        open(os.path.join(temp_dir, ".hidden.wav"), 'w').close()
        
        yield temp_dir
        
        # Cleanup after test
        shutil.rmtree(temp_dir)

    def test_is_audio_file(self):
        """Test is_audio_file function."""
        assert is_audio_file("test.wav", ['.wav']) is True
        assert is_audio_file("test.WAV", ['.wav']) is True
        assert is_audio_file("test.aif", ['.wav']) is False
        assert is_audio_file("test.aif", ['.wav', '.aif']) is True
        assert is_audio_file(".test.wav", ['.wav']) is False
        assert is_audio_file("._test.wav", ['.wav']) is False

    def test_collect_audio_files(self, sample_dir):
        """Test collecting audio files from directory."""
        files = collect_audio_files(sample_dir)
        
        # Should find 4 wav files, sorted alphabetically
        assert len(files) == 4
        assert "kicks/kick1.wav" in files
        assert "kicks/kick2.wav" in files
        assert "snares/snare1.wav" in files
        assert "snares/snare2.wav" in files
        
        # Should not include non-audio files or hidden files
        assert ".hidden.wav" not in files
        assert "readme.txt" not in files

    def test_generate_sfz(self, sample_dir):
        """Test SFZ content generation."""
        audio_files = collect_audio_files(sample_dir)
        sfz_content = generate_sfz(audio_files, start_key=36)
        
        # Verify SFZ content
        lines = sfz_content.strip().split('\n')
        
        # Get the regions (ignoring header comments)
        regions = [line for line in lines if line.startswith('<region>')]
        
        # Check that we have the right number of regions
        assert len(regions) == 4
        
        # Check that all expected files are included (with any key)
        assert any(f"sample=kicks/kick1.wav key=" in r for r in regions)
        assert any(f"sample=kicks/kick2.wav key=" in r for r in regions)
        assert any(f"sample=snares/snare1.wav key=" in r for r in regions)
        assert any(f"sample=snares/snare2.wav key=" in r for r in regions)
        
        # Check that keys are sequential starting from 36
        keys = [int(r.split("key=")[1]) for r in regions]
        assert sorted(keys) == list(range(36, 40))

    def test_generate_sfz_with_group(self):
        """Test SFZ generation with group parameter."""
        audio_files = ["test1.wav", "test2.wav"]
        sfz_content = generate_sfz(audio_files, start_key=60, group_id=1)
        
        lines = sfz_content.strip().split('\n')
        regions = [line for line in lines if line.startswith('<region>')]
        
        assert len(regions) == 2
        assert "<region> sample=test1.wav key=60 group=1" in regions
        assert "<region> sample=test2.wav key=61 group=1" in regions