"""
This file contains helper methods and variables for the cli.py file and its main method.
"""

import argparse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PRECICE_CONFIG_FILE_NAME: str = "precice-config.xml"
GENERATED_DIR_NAME: str = "_generated"
LOG_DIR_NAME: str = ".logs"
DEFAULT_TOPOLOGY_NAME:str = "topology.yaml"



def validate_args(args: argparse.Namespace) -> int:
    """
    Validate the arguments passed to the CLI.
    This checks if the input file exists and is a YAML file.
    :param args: The parsed arguments.
    :return: 0 if the arguments are valid, 1 otherwise.
    """
    logger.debug(f"Arguments parsed. Arguments: {vars(args)}. Checking if given file exists.")

    input_file: Path = Path(args.input_file).resolve()

    # Check if the file exists
    if not input_file.is_file():
        logger.critical(f"File {input_file.resolve()} does not exist. Aborting program.")
        return 1
    logger.debug(f"File {input_file.resolve()} exists.")

    # Check if the file is a YAML file
    if input_file.suffix.lower() in [".yaml", ".yml"]:
        logger.debug(f"File {input_file.resolve()} is a YAML file.")
    else:
        logger.critical(f"File {input_file.resolve()} is not a YAML file. Aborting program.")
        return 1
    return 0
