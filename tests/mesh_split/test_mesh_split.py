"""
Test that meshes are split only when necessary.
This is done by checking whether the generated config file is equivalent to an expected config file.
Additionally, the config is validated using precice-config-check.
"""

from pathlib import Path
import precice_config_graph.graph.operations as operations
from preciceconfigcheck.cli import runCheck

from precicecasegenerate.cli import generate_case

# This directory is the same for all tests in this file.
test_directory: Path = Path(__file__).parent


def test_no_split():
    """
    Here, the exchanges are as follows:
        Fluid --Force(extensive)-> Solid and Solid --Displacement(intensive)-> Fluid
    Even though Fluid and Solid exchange intensive and extensive data, because it is in the same direction,
    the same mesh may be used for both exchanges.
    This means that each participant should only have one mesh.
    """
    case_directory: Path = test_directory / "no_split"
    input_file: Path = case_directory / "topology.yaml"

    assert 0 == generate_case(input_file, case_directory / "_generated"), "Case generation failed."

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert operations.check_config_equivalence(expected, actual), "Configs are not equivalent."
    assert runCheck(actual, True) == 0, "The config failed to validate."

def test_split():
    """
    Here the exchanges are as follows:
       Fluid --Force(extensive),Temperature(intensive)-> SolidA; SolidA --Displacement(intensive)-> Fluid;
       Fluid --Displacement(intensive)-> SolidB; SolidB --Displacement(intensive)-> Fluid
    This means that in the exchange between Fluid and SolidA, intensive and extensive data is exchanged in the same direction,
    i.e., for the communication of Fluid and SolidA, two meshes need to be created (one for intensive and one for extensive).
    For the communication of Fluid and SolidB, only one mesh is needed.
    In total, six meshes are thus needed.
    """
    case_directory: Path = test_directory / "split"
    input_file: Path = case_directory / "topology.yaml"

    assert 0 == generate_case(input_file, case_directory / "_generated"), "Case generation failed."

    expected: Path = case_directory / "precice-config.xml"
    actual: Path = case_directory / "_generated/precice-config.xml"
    assert operations.check_config_equivalence(expected, actual), "Configs are not equivalent."
    assert runCheck(actual, True) == 0, "The config failed to validate."