from .generation_utils.file_generator import FileGenerator
import argparse
import os
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="Takes topology.yaml files as input and writes out needed files to start the precice.")
    parser.add_argument(
        "-f", "--input-file", 
        type=Path, 
        default=Path.cwd() / "topology.yaml",
        help="Input topology.yaml file. Defaults to './topology.yaml'."
    )
    parser.add_argument(
        "-o", "--output-path",
        type=Path,
        help="Output path for the generated folder. Defaults to './_generated'.",
        default=Path.cwd() / "_generated"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )
    parser.add_argument(
        "--validate-topology",
        action="store_true",
        required=False,
        default=True,
        help="Whether to validate the input topology.yaml file against the preCICE topology schema.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    file_generator = FileGenerator(args.input_file, args.output_path)

    # Clear any previous log state
    file_generator.logger.clear_log_state()

    # Generate precice-config.xml, README.md, clean.sh
    file_generator.generate_level_0()
    # Generate configuration for the solvers
    file_generator.generate_level_1()

    # Format the generated preCICE configuration
    file_generator.format_precice_config()
    

    file_generator.handle_output(args)

    file_generator.validate_topology(args)
    


if __name__ == "__main__":
    main()
