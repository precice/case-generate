import os
import sys
import argparse
import shutil

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
    config_str: str = config_creator.create_config_str()
    config_creator.create_config_file(config_str, directory=path_to_generated, filename="precice-config.xml")
    logger.debug("Config creator finished.")

    # TODO other generation steps
    logger.info("Program finished.")
    sys.exit(0)


if __name__ == "__main__":
    main()
