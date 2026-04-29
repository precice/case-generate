import logging
import subprocess
from pathlib import Path
from precice_config_graph import nodes as n
import precice_config_graph.graph.operations as operations

import precicecasegenerate.helper as helper

logger = logging.getLogger(__name__)


class ConfigCreator:
    """
    A class that handles creating preCICE configuration files.
    """

    def __init__(self, config_topology: dict[str, list[n.ParticipantNode] | list[n.DataNode] | list[n.MeshNode]
                                                  | list[n.CouplingSchemeNode] | list[n.MultiCouplingSchemeNode]
                                                  | list[n.M2NNode]]):
        """
        Initialize a ConfigCreator object with a dict that specifies how the preCICE configuration should be created.
        :param config_topology: A dict that contains participants, data nodes, meshes, coupling-schemes and M2N nodes.
        """
        self.config_topology = config_topology

    def validate_config_file(self, filepath: Path = "./precice-config.xml") -> None:
        """
        Validate the preCICE configuration file at the given filepath using precice-config-check.
        The subprocess precice-config-check only checks for logical errors and will crash if there are syntactic errors.
        This means, however, that to pass this check, the configuration file must be syntactically and logically correct :)
        :param filepath: The path to the preCICE configuration file.
        """
        result = subprocess.run(
            ["precice-config-check", filepath],
            capture_output=True,  # capture stdout/stderr
            text=True  # return strings instead of bytes
        )
        # Output = 0 means everything went fine
        if result.returncode == 0:
            logger.debug("preCICE configuration file has been validated with precice-config-check.")
        # Output = 1 means the file was not parsed correctly
        elif result.returncode == 1:
            logger.error(
                f"The generated preCICE configuration file failed to validate with precice-config-check due to syntactic errors:\n"
                f"{''.join('> ' + line for line in result.stderr.splitlines(keepends=True))}\n"
                f"This is likely an error within this program. Please visit {helper.case_generate_repository_url} for more help.")
        # Output = 2 means the file was parsed correctly but contains logical errors
        elif result.returncode == 2:
            logger.error(
                f"The generated preCICE configuration file failed to validate with precice-config-check due to logical errors:\n"
                f"{''.join('> ' + line for line in result.stdout.splitlines(keepends=True))}\n"
                f"This is likely an error within this program. "
                f"You can either try to fix the configuration file yourself or visit "
                f"{helper.case_generate_repository_url} for more help.")

    def create_config_file(self, directory: Path = ".", filename: str = "precice-config.xml") -> None:
        """
        Create a configuration file.
        The file is saved in the given directory with the given filename.
        :param directory: The directory to save the file in.
        :param filename: The filename of the file.
        """
        # Convert to Path object just in case
        directory = Path(directory)
        file_path: Path = directory / filename
        operations.create_config_file_from_dict(self.config_topology, path=directory, filename=filename)
        logger.info(f"preCICE configuration file written to {file_path}")
