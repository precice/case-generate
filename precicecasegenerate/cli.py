import os
import sys
import argparse
import shutil

from precicecasegenerate.adapter_config_creator.adapter_config_creator import AdapterConfigCreator
from precicecasegenerate.logging_setup import setup_logging
from precicecasegenerate.config_creator.node_creator import NodeCreator
from precicecasegenerate.config_creator.config_creator import ConfigCreator
from precicecasegenerate.input_handler.topology_reader import TopologyReader


def main():
    logger = setup_logging()
    logger.info("Program started.")

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "file_path",
        type=str,
        help="Path to the input YAML file."
    )
    logger.debug("Parsing arguments.")
    args = parser.parse_args()
    logger.debug(f"Arguments parsed. Arguments: {vars(args)}. Checking if given file exists.")

    # Check if the file exists
    if not os.path.isfile(args.file_path):
        logger.critical(f"File {os.path.abspath(args.file_path)} does not exist. Aborting program.")
        sys.exit(1)
    logger.debug("File exists.")

    # Check if the file is a YAML file
    _, ext = os.path.splitext(args.file_path)
    if ext.lower() in [".yaml", ".yml"]:
        logger.debug("File is a YAML file.")
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

    # TODO create subdirectories for solvers here
    participant_solver_map: dict = node_creator.get_participant_solver_map()
    for participant in participant_solver_map:
        participant_directory: str = (path_to_generated.lower() + participant.name.lower() + "-"
                                      + participant_solver_map[participant].lower() + "/")
        # The directory will be overwritten if it already exists and is of the form "_generated/name-solver/"
        shutil.rmtree(participant_directory, ignore_errors=True)
        os.makedirs(participant_directory, exist_ok=True)

    logger.debug("Starting adapter config creator.")
    mesh_patch_map: dict = node_creator.get_mesh_patch_map()
    adapter_config_creator: AdapterConfigCreator = AdapterConfigCreator(participant_solver_map, mesh_patch_map)
    adapter_config_creator.create_adapter_configs(parent_directory=path_to_generated)

    # TODO create run.sh for solvers here

    # TODO create clean.sh here

    logger.info("Program finished.")
    sys.exit(0)


if __name__ == "__main__":
    main()
