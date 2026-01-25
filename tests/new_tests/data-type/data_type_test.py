"""
Test that the data-type tag of exchanges works as intended.
This is done by checking whether the generated config file is equivalent to an expected config file.
Additionally, the config is validated using precice-config-check.
"""

from pathlib import Path
from precice_config_graph.graph import check_config_equivalence
from preciceconfigcheck.cli import runCheck

from precicecasegenerate.cli import generate_case

# This directory is the same for all tests in this file.
test_directory: Path = Path(__file__).parent


def test_same_type_one_direction():
    """
    This is the simplest case.
    There is only one exchange and thus only one data-type.
    Nothing should go wrong here.
    """
    case_directory: Path = test_directory / "same_type_one_direction"
    input_file: Path = case_directory / "topology.yaml"

    generate_case(input_file, case_directory)

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert check_config_equivalence(expected, actual), "Configs are not equivalent."
    assert runCheck(actual, True) == 0, "The config failed to validate."


def test_different_type_one_direction():
    """
    This case is more complex.
    There are two exchanges with different data-types.
    Thus, two different data nodes should be created, with names ending in "-Vector" and "-Scalar" respectively.
    """
    case_directory: Path = test_directory / "different_type_one_direction"
    input_file: Path = case_directory / "topology.yaml"

    generate_case(input_file, case_directory)

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert check_config_equivalence(expected, actual), "Configs are not equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."


def test_same_type_both_directions():
    """
    This case is more complex.
    There are two exchanges, one per direction, with the same data-type.
    This should result in two data-nodes, one with a "uniquified" name.
    """
    case_directory: Path = test_directory / "same_type_both_directions"
    input_file: Path = case_directory / "topology.yaml"

    generate_case(input_file, case_directory)

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert not check_config_equivalence(expected, actual), "Configs are equivalent with different names."
    assert check_config_equivalence(expected, actual, ignore_names=True), "Configs not are equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."


def test_different_type_both_directions():
    """
    This case is more complex.
    There are two exchanges, one per direction, with different data-types.
    This should result in two data-nodes, with names ending in "-Vector" and "-Scalar" respectively.
    """
    case_directory: Path = test_directory / "different_type_both_directions"
    input_file: Path = case_directory / "topology.yaml"

    generate_case(input_file, case_directory)

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert check_config_equivalence(expected, actual), "Configs are not equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."


def test_both_types_both_directions():
    """
    This case is the most complex.
    There are six exchanges and now three participants, A, B and C.
    A and B share four exchanges, which should result in four data nodes;
    and B and C share two exchanges, which should reuse the same data nodes.
    This should result in four data-nodes, two with "uniquified" names.
    """
    case_directory: Path = test_directory / "both_types_both_directions"
    input_file: Path = case_directory / "topology.yaml"

    generate_case(input_file, case_directory)

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert not check_config_equivalence(expected, actual), "Configs are equivalent with different names."
    assert check_config_equivalence(expected, actual, ignore_names=True), "Configs are not equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."
