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
DEFAULT_TOPOLOGY_NAME: str = "topology.yaml"


def yaml_file(filepath: str) -> Path:
    """
    Check if the filepath points to an existing YAML file.
    Otherwise, raise an argparse.ArgumentTypeError.
    :param filepath: The path to the input file as a string.
    :return: The path to the input file as a Path object.
    """
    input_file = Path(filepath).resolve()

    # Check if the file exists
    if not input_file.is_file():
        logger.critical(f"File {input_file.resolve()} does not exist. Aborting program.")
        raise argparse.ArgumentTypeError(f"File '{input_file.resolve()}' does not exist.")
    logger.debug(f"File {input_file.resolve()} exists.")

    # Check if the file is a YAML file
    if input_file.suffix.lower() not in [".yaml", ".yml"]:
        logger.critical(f"File {input_file.resolve()} is not a YAML file. Aborting program.")
        raise argparse.ArgumentTypeError(f"The file '{input_file}' is not a YAML file.")
    logger.debug(f"File {input_file.resolve()} is a YAML file.")

    return input_file
