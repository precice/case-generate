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


def makeGenerateParser(add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize a preCICE case given a topology file",
        add_help=add_help,
    )
    parser.add_argument(
        "input_file",
        type=Path,
        nargs="?",
        help="Path to the input YAML topology file.",
        default=Path("topology.yaml")
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging output."
    )
    parser.add_argument(
        "-o", "--output_path",
        type=Path,
        default=Path(GENERATED_DIR_NAME),
        help="A custom output path for the generated folder. Already existing folders and files will be overwritten."
    )
    return parser


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
