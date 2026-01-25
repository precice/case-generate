"""
This file contains helper methods and variables for the cli.py file and its main method.
"""

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

PRECICE_CONFIG_FILE_NAME: str = "precice-config.xml"
GENERATED_DIR_NAME: str = "_generated"
LOG_DIR_NAME: str = ".logs"


def get_args() -> argparse.Namespace:
    """
    Get the arguments passed to the CLI.
    :return: An argparse namespace.
    """
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
    return parser.parse_args()


def validate_args(args: argparse.Namespace):
    """
    Validate the arguments passed to the CLI.
    This checks if the input file exists and is a YAML file.
    :param args: The parsed arguments.
    """
    logger.debug(f"Arguments parsed. Arguments: {vars(args)}. Checking if given file exists.")

    input_file: Path = Path(args.file_path)

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
