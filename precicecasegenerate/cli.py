from .generation_utils.file_generator import FileGenerator
import argparse
import sys
from pathlib import Path


def makeGenerateParser(add_help: bool = True):
    parser = argparse.ArgumentParser(
        description="Initialize a preCICE case given a topology file",
        add_help=add_help,
    )
    parser.add_argument(
        "-f",
        "--input-file",
        type=Path,
        default=Path.cwd() / "topology.yaml",
        help="Input topology.yaml file. Defaults to './topology.yaml'.",
    )
    parser.add_argument(
        "-o",
        "--output-path",
        type=Path,
        help="Output path for the generated folder. Defaults to './_generated'.",
        default=Path.cwd() / "_generated",
    )
    parser.add_argument(
        "-v",
        "--verbose",
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
    return parser


def runGenerate(ns):
    try:
        file_generator = FileGenerator(ns.input_file, ns.output_path)

        # Clear any previous log state
        file_generator.logger.clear_log_state()

        # Generate precice-config.xml, README.md, clean.sh
        file_generator.generate_level_0()
        # Generate configuration for the solvers
        file_generator.generate_level_1()

        # Format the generated preCICE configuration
        file_generator.format_precice_config()

        file_generator.handle_output(ns)

        file_generator.validate_topology(ns)

        return 0
    except Exception as e:
        print(e, file=sys.stderr)
        return 1


def main():
    args = makeGenerateParser().parse_args()
    return runGenerate(args)


if __name__ == "__main__":
    sys.exit(main())
