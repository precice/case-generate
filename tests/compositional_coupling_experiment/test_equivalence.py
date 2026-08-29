"""
Test that exchanges between participants correctly lead to data renaming if only the specified patches are unique.
"""

from pathlib import Path
from precice_config_graph.graph import operations
from preciceconfigcheck.cli import runCheck

from precicecasegenerate.cli import generate_case

# This directory is the same for all tests in this file.
test_directory: Path = Path(__file__).parent
def test_compositional_coupling_experiment():
    """
    Test if the created config-file matches the expected one.
    """
    case_directory: Path = test_directory
    input_file: Path = case_directory / "topology.yaml"

    assert 0 == generate_case(input_file, case_directory / "_generated"), "Case generation failed."

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert not operations.check_config_equivalence(expected, actual), "Configs are equivalent with different naming."
    assert operations.check_config_equivalence(expected, actual, ignore_names=True), "Configs are not equivalent up to naming."
    assert runCheck(actual, True) == 0, "The config failed to validate."
