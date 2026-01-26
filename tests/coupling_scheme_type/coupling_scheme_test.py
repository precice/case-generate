"""
Test that coupling-schemes are created correctly according to the topology.
"""

from pathlib import Path
from precice_config_graph.graph import check_config_equivalence
from preciceconfigcheck.cli import runCheck

from precicecasegenerate.cli import generate_case

# This directory is the same for all tests in this file.
test_directory: Path = Path(__file__).parent


def test_explicit_coupling_scheme():
    """
    Test that an explicit coupling-scheme is created.
    """
    case_directory: Path = test_directory / "explicit_coupling"
    input_file_two_participants: Path = case_directory / "two-participants.yaml"

    generate_case(input_file_two_participants, case_directory)

    expected: Path = case_directory / "precice-config_two-participants.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert check_config_equivalence(expected, actual, ignore_names=True), "Configs are not equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."

    input_file_three_participants: Path = case_directory / "three-participants.yaml"
    # The previous files are overwritten
    generate_case(input_file_three_participants, case_directory)

    expected: Path = case_directory / "precice-config_three-participants.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert check_config_equivalence(expected, actual, ignore_names=True), "Configs are not equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."

def test_implicit_coupling_scheme():
    """
    Test that an implicit coupling-scheme is created.
    """
    case_directory: Path = test_directory / "implicit_coupling"
    input_file: Path = case_directory / "topology.yaml"

    generate_case(input_file, case_directory)

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert check_config_equivalence(expected, actual, ignore_names=True), "Configs are not equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."

def test_multi_coupling_scheme():
    """
    Test that a multi-coupling scheme is created.
    """
    case_directory: Path = test_directory / "multi_coupling"
    input_file: Path = case_directory / "topology.yaml"

    generate_case(input_file, case_directory)

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert check_config_equivalence(expected, actual, ignore_names=True), "Configs are not equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."