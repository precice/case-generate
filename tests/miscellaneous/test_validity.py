"""
This file contains tests for the validity of the generated preCICE config files.
"""

from pathlib import Path
from preciceconfigcheck.cli import runCheck

from precicecasegenerate.cli import generate_case

# This directory is the same for all tests in this file.
test_directory: Path = Path(__file__).parent


def test_validity():
    """
    Check that all topologies generate valid preCICE config files.
    """
    for case_directory in test_directory.iterdir():
        # Ignore files and folders like __pycache__/
        if not case_directory.is_dir() or case_directory.name.startswith("__"):
            continue

        input_file: Path = case_directory / "topology.yaml"

        assert 0 == generate_case(input_file, case_directory), "Case generation failed."

        config_file: Path = case_directory / "_generated/precice-config.xml"
        assert runCheck(config_file, True) == 0, "The config failed to validate."
