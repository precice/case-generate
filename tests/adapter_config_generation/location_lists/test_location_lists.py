import json
from pathlib import Path
from ruamel.yaml import YAML

from precicecasegenerate.cli import generate_case


def test_location_lists():
    """
    Test that the location lists are created correctly.
    """
    case_directory: Path = Path(__file__).parent
    input_file: Path = case_directory / "topology.yaml"
    generated_dir: Path = case_directory / "_generated"

    assert 0 == generate_case(input_file, generated_dir), "Case generation failed."

    # Read topology
    yaml = YAML(typ="safe")
    with open(input_file, "r") as f:
        topology = yaml.load(f)

    # Map each participant to their expected list of locations
    expected_locations: dict[str, list[str]] = {}
    for exchange in topology["exchanges"]:
        expected_locations[exchange["from"]] = exchange["from-location-names"]
        expected_locations[exchange["to"]] = exchange["to-location-names"]

    # Iterate over solver directories
    for solver_directory in generated_dir.iterdir():
        # Exclude files, pycache, hidden folders, etc.
        if not solver_directory.is_dir() or solver_directory.name.startswith("__") or solver_directory.name.startswith(
                "."):
            continue

        config_path = solver_directory / "adapter-config.json"
        assert config_path.exists(), f"Adapter config missing in {solver_directory.name}"

        with open(config_path, "r") as f:
            adapter_config = json.load(f)

        # Check who this config belongs to
        participant_name = adapter_config["participant_name"]

        # Store the generated locations
        actual_locations = adapter_config["interfaces"][0]["location_names"]

        # Check that participant was defined
        assert participant_name in expected_locations, f"Unexpected participant {participant_name} found."

        # Check that the locations are correct
        assert actual_locations == expected_locations[participant_name], (
            f"Location mismatch for {participant_name}. "
            f"Expected: {expected_locations[participant_name]}, actual: {actual_locations}."
        )
