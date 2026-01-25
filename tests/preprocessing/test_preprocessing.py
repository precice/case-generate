"""
This file tests that the preprocessing works as expected.
"""
from pathlib import Path

from precicecasegenerate.cli import generate_case

# This directory is the same for all tests in this file.
test_directory: Path = Path(__file__).parent


def test_duplicate_participant_names():
    """
    Test that an error is raised when two participants have the same name.
    """
    case_directory: Path = test_directory / "duplicate_participants"
    input_file: Path = case_directory / "topology.yaml"

    assert 0 != generate_case(input_file, case_directory), "The case generation didn't fail."


def test_unknown_participant_names():
    """
    Test that an error is raised when a participant is mentioned in an exchange but not defined in the topology.
    """
    case_directory: Path = test_directory / "unknown_participants"
    input_file: Path = case_directory / "topology.yaml"

    assert 0 != generate_case(input_file, case_directory), "The case generation didn't fail."


def test_duplicate_exchanges():
    """
    Test that an error is raised when two exchanges have the exact same items.
    """
    case_directory: Path = test_directory / "duplicate_exchanges"
    input_file: Path = case_directory / "topology.yaml"

    assert 0 != generate_case(input_file, case_directory), "The case generation didn't fail."
