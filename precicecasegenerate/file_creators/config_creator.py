import logging
import subprocess
from precice_config_graph import nodes as n

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

    def _create_config_str(self) -> str:
        """
        Create a string representing a preCICE configuration file.
        This is done by iterating over the given topology dict and creating a string for each element.
        :return: A string representing a preCICE configuration file.
        """
        # "Header" information
        config_str: str = (f"<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n"
                           f"<precice-configuration>\n"
                           f"  <log>\n"
                           f"    <sink\n"
                           f"      filter=\"%Severity% > debug\"\n"
                           f"      format=\"---[precice] %ColorizedSeverity% %Message%\"\n"
                           f"      enabled=\"true\" />\n"
                           f"  </log>\n\n")  # two newlines to separate the header from the content

        for data in self.config_topology["data"]:
            config_str += f"  " + data.to_xml() + "\n"

        config_str += "\n"  # separate mesh from data

        mesh_str: str = ""
        for mesh in self.config_topology["meshes"]:
            mesh_str += f"{mesh.to_xml()}"
        config_str += "".join("  " + line for line in mesh_str.splitlines(keepends=True))

        config_str += "\n"  # separate mesh from participants

        participant_str: str = ""
        for participant in self.config_topology["participants"]:
            participant_str += f"{participant.to_xml()}"
        config_str += "".join("  " + line for line in participant_str.splitlines(keepends=True))

        config_str += "\n"  # separate participants from coupling-schemes

        coupling_scheme_str: str = ""
        for coupling_scheme in self.config_topology["coupling-schemes"]:
            coupling_scheme_str += f"{coupling_scheme.to_xml()}"
        config_str += "".join("  " + line for line in coupling_scheme_str.splitlines(keepends=True))

        config_str += "\n"  # separate coupling-schemes from m2ns

        for m2n in self.config_topology["m2n"]:
            config_str += f"  {m2n.to_xml()}"

        config_str += f"\n</precice-configuration>"
        return config_str

    def _validate_config_file(self, filepath: str = "./precice-config.xml") -> None:
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
                f"{"".join("> " + line for line in result.stderr.splitlines(keepends=True))}\n"
                f"This is likely an error within this program. Please visit {helper.case_generate_repository_url} for more help.")
        # Output = 2 means the file was parsed correctly but contains logical errors
        elif result.returncode == 2:
            logger.error(
                f"The generated preCICE configuration file failed to validate with precice-config-check due to logical errors:\n"
                f"{"".join("> " + line for line in result.stdout.splitlines(keepends=True))}\n"
                f"This is likely an error within this program. "
                f"You can either try to fix the configuration file yourself or visit "
                f"{helper.case_generate_repository_url} for more help.")

    def create_config_file(self, directory: str = "./", filename: str = "precice-config.xml") -> None:
        """
        Create a configuration file.
        The file is saved in the given directory with the given filename.
        :param directory: The directory to save the file in.
        :param filename: The filename of the file.
        """
        with open(directory + filename, "w") as f:
            f.write(self._create_config_str())
        logger.info(f"preCICE configuration file written to {directory + filename}")
        self._validate_config_file(filepath=directory + filename)
