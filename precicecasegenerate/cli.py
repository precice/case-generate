import os
import sys
import argparse
import shutil

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
    args = parser.parse_args()

    logger = setup_logging(verbose=args.verbose)
    logger.info("Program started.")

    logger.debug(f"Arguments parsed. Arguments: {vars(args)}. Checking if given file exists.")

    # Check if the file exists
    if not os.path.isfile(args.file_path):
        logger.critical(f"File {os.path.abspath(args.file_path)} does not exist. Aborting program.")
        sys.exit(1)
    logger.debug(f"File {args.file_path} exists.")

    # Check if the file is a YAML file
    _, ext = os.path.splitext(args.file_path)
    if ext.lower() in [".yaml", ".yml"]:
        logger.debug(f"File {args.file_path} is a YAML file.")
    else:
        logger.critical(f"File {os.path.abspath(args.file_path)} is not a YAML file. Aborting program.")

    # Create a new directory for the generated files
    path_to_generated: str = "_generated/"
    logger.debug(f"Resetting generated files at {os.path.abspath(path_to_generated)}.")
    # Ignore errors if the directory does not exist
    shutil.rmtree(path_to_generated, ignore_errors=True)
    os.makedirs(path_to_generated)

    logger.debug("Starting topology reader.")
    topology_reader: TopologyReader = TopologyReader(args.file_path)
    topology: dict = topology_reader.get_topology()
    logger.debug("Topology reader finished.")

    logger.debug("Starting node creator.")
    node_creator: NodeCreator = NodeCreator(topology)
    nodes: dict = node_creator.get_nodes()
    logger.debug("Node creator finished.")

    logger.debug("Starting config creator.")
    config_creator: ConfigCreator = ConfigCreator(nodes)
    config_creator.create_config_file(directory=path_to_generated, filename="precice-config.xml")
    logger.debug("Config creator finished.")

    logger.debug("Creating participant directories.")
    participant_solver_map: dict = node_creator.get_participant_solver_map()
    for participant in participant_solver_map:
        participant_directory: str = helper.get_participant_solver_directory(path_to_generated, participant.name,
                                                                             participant_solver_map[participant])
        # The directory will be overwritten if it already exists and is of the form "_generated/name-solver/"
        shutil.rmtree(participant_directory, ignore_errors=True)
        os.makedirs(participant_directory, exist_ok=True)
        logger.debug(f"Created participant directory at {participant_directory}")

    logger.debug("Starting adapter config creator.")
    mesh_patch_map: dict = node_creator.get_mesh_patch_map()
    adapter_config_creator: AdapterConfigCreator = AdapterConfigCreator(participant_solver_map, mesh_patch_map)
    adapter_config_creator.create_adapter_configs(parent_directory=path_to_generated)

    logger.debug("Starting utility file creator.")
    utility_file_creator: UtilityFileCreator = UtilityFileCreator(participant_solver_map)
    utility_file_creator.create_utility_files(parent_directory=path_to_generated)

    logger.info("Program finished.")
    sys.exit(0)


if __name__ == "__main__":
    main()
