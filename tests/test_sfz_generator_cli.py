"""
Integration test for SFZ Generator CLI tool.
"""

import os
import tempfile
import shutil
import subprocess
import sys
import pytest


@pytest.fixture
def sample_dir():
    """Create a temporary directory with sample audio files."""
    temp_dir = tempfile.mkdtemp()
    
    # Create subdirectories and files
    os.makedirs(os.path.join(temp_dir, "kicks"))
    open(os.path.join(temp_dir, "kicks", "kick1.wav"), 'w').close()
    open(os.path.join(temp_dir, "kicks", "kick2.wav"), 'w').close()
    
    # Create some non-audio files to be ignored
    open(os.path.join(temp_dir, "readme.txt"), 'w').close()
    
    yield temp_dir
    
    # Cleanup after test
    shutil.rmtree(temp_dir)


def test_sfz_generator_cli(sample_dir):
    """Test the command line interface of the SFZ generator."""
    output_sfz = os.path.join(sample_dir, "output.sfz")
    
    # Build the command to run the script
    script_path = os.path.join("src", "python", "utils", "sfz", "generate_sfz.py")
    cmd = [
        sys.executable, 
        script_path,
        "-i", sample_dir,
        "-o", output_sfz,
        "--start-key", "48",
        "--verbose"
    ]
    
    # Run the command
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Check if the command completed successfully
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    
    # Check if output file was created
    assert os.path.exists(output_sfz), "Output SFZ file was not created"
    
    # Check the content of the generated SFZ file
    with open(output_sfz, 'r') as f:
        content = f.read()
    
    # Verify the content includes our samples with the right keys
    assert "<region> sample=kicks/kick1.wav key=48" in content
    assert "<region> sample=kicks/kick2.wav key=49" in content