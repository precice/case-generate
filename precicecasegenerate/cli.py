import sys
import shutil
import logging
import argparse
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


def runGenerate(args: argparse.Namespace) -> int:
    setup_logging(verbose=args.verbose)
    logger.info("Program started.")

    return_value: int = cli_helper.validate_args(args)
    if return_value != 0:
        return return_value

    input_file: Path = Path(args.input_file)
    output_root: Path = Path(args.output_path)

    return_value = generate_case(input_file, output_root)

    logger.info("Program finished.")
    return return_value


def generate_case(input_file: Path, output_root: Path) -> int:
    """
    Generate all files for a preCICE case
    This method creates the required directories and calls the respective methods to create the nodes from the topology,
    the preCICE configuration file, the adapter configuration files, and the utility files.
    :param input_file: The path to the input file containing the topology.
    :param output_root: The root directory for the generated files.
    :return: 0 if successful, 1 otherwise.
    """
    # Create a new directory for the generated files
    output_root.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created output directory at {output_root}")

    logger.debug("Starting topology reader.")
    topology_reader: TopologyReader = TopologyReader(input_file.resolve())
    return_value: int = topology_reader.validate_topology()
    if return_value != 0:
        return return_value
    return_value: int = topology_reader.check_topology()
    if return_value != 0:
        return return_value
    topology: dict = topology_reader.get_topology()
    logger.debug("Topology reader finished.")

    logger.debug("Starting node creator.")
    node_creator: NodeCreator = NodeCreator(topology)
    nodes: dict = node_creator.get_nodes()
    logger.debug("Node creator finished.")

    logger.debug("Starting config creator.")
    config_creator: ConfigCreator = ConfigCreator(nodes)
    config_creator.create_config_file(directory=output_root, filename=cli_helper.PRECICE_CONFIG_FILE_NAME)
    logger.debug("Config creator finished.")

    logger.debug("Creating participant directories.")
    participant_solver_map: dict = node_creator.get_participant_solver_map()
    for participant in participant_solver_map:
        participant_directory: Path = helper.get_participant_solver_directory(output_root, participant.name,
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
    adapter_config_creator.create_adapter_configs(parent_directory=output_root)

    logger.debug("Starting utility file creator.")
    utility_file_creator: UtilityFileCreator = UtilityFileCreator(participant_solver_map)
    utility_file_creator.create_utility_files(parent_directory=output_root)
    return 0


def main() -> int:
    # Parse the command line arguments
    parser = cli_helper.makeGenerateParser()
    args = parser.parse_args()
    return runGenerate(args)


if __name__ == "__main__":
    sys.exit(main())
