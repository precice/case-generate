"""
Test that exchanges between participants correctly lead to data renaming if only the specified patches are unique.
"""

from pathlib import Path
from precice_config_graph.graph import operations
from preciceconfigcheck.cli import runCheck

from precicecasegenerate.cli import generate_case

# This directory is the same for all tests in this file.
test_directory: Path = Path(__file__).parent
def test_data_renaming():
    """
    Test that the data is renamed correctly when exchanges are not unique if patches are disregarded;
    i.e., if from, to, type, data, data-type, is not unique in the topology,
    then the non-unique exchanges need their data renamed.
    """
    case_directory: Path = test_directory
    input_file: Path = case_directory / "topology.yaml"

    generate_case(input_file, case_directory / "_generated")

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert not operations.check_config_equivalence(expected, actual), "Configs are equivalent with different names."
    assert operations.check_config_equivalence(expected, actual, ignore_names=True), "Configs not are equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."