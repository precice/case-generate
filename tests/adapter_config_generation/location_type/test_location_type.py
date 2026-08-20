"""
This file contains tests for the validity of the generated preCICE config files.
"""

from pathlib import Path
import json

from precicecasegenerate.cli import generate_case

# This directory is the same for all tests in this file.
test_directory: Path = Path(__file__).parent


def test_location_type():
    """
    Check the adapter config has the correct location-type.
    """
    for case_directory in test_directory.iterdir():
        # Ignore files and folders like __pycache__/
        if not case_directory.is_dir() or case_directory.name.startswith("__") or case_directory.name.startswith("."):
            continue

        input_file: Path = case_directory / "topology.yaml"

        assert 0 == generate_case(input_file, case_directory / "_generated"), "Case generation failed."

        generated_directory: Path = case_directory / "_generated"
        for solver_directory in generated_directory.iterdir():
            # Ignore weird folders and files
            if not solver_directory.is_dir() or solver_directory.name.startswith(
                    "__") or solver_directory.name.startswith("."):
                continue
            adapter_config_file: Path = solver_directory / "adapter-config.json"
            with open(adapter_config_file, "r") as f:
                adapter_config = json.load(f)

            interfaces: list = adapter_config["interfaces"]
            # The case_directory.name is the name of the location
            assert interfaces[0]["location"] == case_directory.name
