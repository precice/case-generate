import sys
import shutil
import logging
from logging import Logger
from pathlib import Path

from precicecasegenerate import helper
from precicecasegenerate import cli_helper
from precicecasegenerate.logging_setup import setup_logging
from precicecasegenerate.input_handler.topology_reader import TopologyReader
from precicecasegenerate.node_creator import NodeCreator
from precicecasegenerate.file_creators.config_creator import ConfigCreator
from precicecasegenerate.file_creators.adapter_config_creator import AdapterConfigCreator
from precicecasegenerate.file_creators.utility_file_creator import UtilityFileCreator

logger = logging.getLogger(__name__)


def main():
    args = cli_helper.get_args()

    setup_logging(verbose=args.verbose)
    logger.info("Program started.")

    cli_helper.validate_args(args)

    input_file: Path = Path(args.file_path)
    output_root: Path = Path(args.output_path)

    generate_case(input_file, output_root)

    logger.info("Program finished.")
    sys.exit(0)


def generate_case(input_file: Path, output_root: Path):
    """
    Generate all files for a preCICE case
    This method creates the required directories and calls the respective methods to create the nodes from the topology,
    the preCICE configuration file, the adapter configuration files, and the utility files.
    :param input_file: The path to the input file containing the topology.
    :param output_root: The root directory for the generated files.
    """
    # Create a new directory for the generated files
    generated_dir: Path = output_root / cli_helper.GENERATED_DIR_NAME
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
    config_creator.create_config_file(directory=generated_dir, filename=cli_helper.PRECICE_CONFIG_FILE_NAME)
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
                                                                        precice_config_filename=cli_helper.PRECICE_CONFIG_FILE_NAME)
    adapter_config_creator.create_adapter_configs(parent_directory=generated_dir)

    logger.debug("Starting utility file creator.")
    utility_file_creator: UtilityFileCreator = UtilityFileCreator(participant_solver_map)
    utility_file_creator.create_utility_files(parent_directory=generated_dir)


if __name__ == "__main__":
    main()
