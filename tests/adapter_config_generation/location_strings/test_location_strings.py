from pathlib import Path

from precicecasegenerate.cli import generate_case


def test_location_strings():
    case_directory: Path = Path(__file__).parent
    input_file: Path = case_directory / "topology.yaml"

    assert 0 != generate_case(input_file, case_directory / "_generated"), "Case generation did not fail."
