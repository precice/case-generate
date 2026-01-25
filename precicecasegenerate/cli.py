import os
import sys
import argparse
import shutil
from pathlib import Path

from precicecasegenerate.logging_setup import setup_logging
from precicecasegenerate import helper
from precicecasegenerate.input_handler.topology_reader import TopologyReader
from precicecasegenerate.node_creator import NodeCreator
from precicecasegenerate.file_creators.config_creator import ConfigCreator
from precicecasegenerate.file_creators.adapter_config_creator import AdapterConfigCreator
from precicecasegenerate.file_creators.utility_file_creator import UtilityFileCreator


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "file_path",
        type=str,
        help="Path to the input YAML file."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output."
    )
    parser.add_argument(
        "-o", "--output_path",
        type=str,
        default="./",
        help="A custom output path for the generated files."
    )
    args = parser.parse_args()

    logger = setup_logging(verbose=args.verbose)
    logger.info("Program started.")

    logger.debug(f"Arguments parsed. Arguments: {vars(args)}. Checking if given file exists.")

    PRECICE_CONFIG_FILE_NAME: str = "precice-config.xml"

    input_file: Path = Path(args.file_path)
    output_root: Path = Path(args.output_path)

    # Check if the file exists
    if not input_file.is_file():
        logger.critical(f"File {input_file.resolve()} does not exist. Aborting program.")
        sys.exit(1)
    logger.debug(f"File {input_file.resolve()} exists.")

    # Check if the file is a YAML file
    if input_file.suffix.lower() in [".yaml", ".yml"]:
        logger.debug(f"File {input_file.resolve()} is a YAML file.")
    else:
        logger.critical(f"File {input_file.resolve()} is not a YAML file. Aborting program.")

    # Create a new directory for the generated files
    generated_dir: Path = output_root / "_generated"
    logger.debug(f"Resetting generated files at {generated_dir.resolve()}.")
    # Remove the directory if it already exists
    if generated_dir.exists():
        shutil.rmtree(generated_dir, ignore_errors=True)
    generated_dir.mkdir(parents=True, exist_ok=True)

    logger.debug("Starting topology reader.")
    topology_reader: TopologyReader = TopologyReader(str(input_file.resolve()))
    topology: dict = topology_reader.get_topology()
    logger.debug("Topology reader finished.")

    logger.debug("Starting node creator.")
    node_creator: NodeCreator = NodeCreator(topology)
    nodes: dict = node_creator.get_nodes()
    logger.debug("Node creator finished.")

    logger.debug("Starting config creator.")
    config_creator: ConfigCreator = ConfigCreator(nodes)
    config_creator.create_config_file(directory=generated_dir, filename=PRECICE_CONFIG_FILE_NAME)
    logger.debug("Config creator finished.")

    logger.debug("Creating participant directories.")
    participant_solver_map: dict = node_creator.get_participant_solver_map()
    for participant in participant_solver_map:
        participant_directory: Path = helper.get_participant_solver_directory(generated_dir, participant.name,
                                                                              participant_solver_map[participant])
        # The directory will be overwritten if it already exists and is of the form "_generated/name-solver/"
        if participant_directory.exists():
            shutil.rmtree(participant_directory, ignore_errors=True)
        participant_directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created participant directory at {participant_directory}")

    logger.debug("Starting adapter config creator.")
    mesh_patch_map: dict = node_creator.get_mesh_patch_map()
    adapter_config_creator: AdapterConfigCreator = AdapterConfigCreator(participant_solver_map,
                                                                        mesh_patch_map,
                                                                        precice_config_filename=PRECICE_CONFIG_FILE_NAME)
    adapter_config_creator.create_adapter_configs(parent_directory=generated_dir)

    logger.debug("Starting utility file creator.")
    utility_file_creator: UtilityFileCreator = UtilityFileCreator(participant_solver_map)
    utility_file_creator.create_utility_files(parent_directory=generated_dir)

    logger.info("Program finished.")
    sys.exit(0)


if __name__ == "__main__":
    main()
