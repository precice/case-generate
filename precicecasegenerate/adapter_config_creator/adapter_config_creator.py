import logging

from precice_config_graph import nodes as n

logger = logging.getLogger(__name__)


class AdapterConfigCreator:
    """
    A class that handles creating adapter configuration files for participants in the correct directory.
    """

    def __init__(self, participant_solver_map: dict[n.ParticipantNode, str],
                 mesh_patch_map: dict[n.MeshNode, set[str]]):
        """
        Initialize an AdapterConfigCreator object, which creates adapter configuration files for each participant.
        :param participant_solver_map: A dict mapping participant nodes to their solver names.
        :param mesh_patch_map: A map mapping meshes to sets of patches.
        """
        self.participant_solver_map = participant_solver_map
        self.patch_map = mesh_patch_map

    def _create_adapter_config_str(self, participant: n.ParticipantNode,
                                   mesh_patch_map: dict[n.MeshNode, set[str]]) -> str:
        """
        Create a string representing the adapter configuration file for the given participant and mesh-patch map.
        :param participant: The participant for which the adapter configuration file is created.
        :param mesh_patch_map: A dict mapping meshes to sets of patches that they use.
        :return: A string representing the adapter configuration file for the given participant and mesh-patch map.
        """
        indent: str = "\t"

        indent_lvl: int = 0
        adapter_config_str: str = f"{{\n"
        indent_lvl += 1
        adapter_config_str += f"{indent_lvl * indent}\"participant_name\": \"{participant.name}\",\n"
        adapter_config_str += f"{indent_lvl * indent}\"precice_config_file_name\": \"../precice-config.xml\",\n"
        adapter_config_str += f"{indent_lvl * indent}\"interfaces\": [\n"
        indent_lvl += 1
        # Create an entry for each mesh
        # We can use provide meshes here, as there are no "api-access" meshes,
        # i.e., a participant always reads from and writes to their own mesh
        for mesh in participant.provide_meshes:
            adapter_config_str += f"{indent_lvl * indent}{{\n"
            indent_lvl += 1
            adapter_config_str += f"{indent_lvl * indent}\"mesh_name\": \"{mesh.name}\",\n"
            # Create an entry for each patch
            adapter_config_str += "".join(indent_lvl * indent + line for line in
                                          self._get_patch_string(mesh, mesh_patch_map).splitlines(keepends=True))
            # Create an entry for each read-data
            adapter_config_str += "".join(indent_lvl * indent + line for line in
                                          self._get_read_data_string(participant, mesh).splitlines(keepends=True))
            # Create an entry for each write-data
            adapter_config_str += "".join(indent_lvl * indent + line for line in
                                          self._get_write_data_string(participant, mesh).splitlines(keepends=True))
            adapter_config_str = adapter_config_str.rstrip(",\n")
            adapter_config_str += "\n"
            indent_lvl -= 1
            adapter_config_str += f"{indent_lvl * indent}}},\n"
            logger.debug(f"Created adapter configuration entry for mesh {mesh.name} in participant "
                         f"{participant.name}'s adapter-config.")
        # Remove the trailing comma
        adapter_config_str = adapter_config_str.rstrip(",\n")
        # Add the linebreak again
        adapter_config_str += f"\n"
        indent_lvl -= 1
        adapter_config_str += f"{indent_lvl * indent}]\n"
        indent_lvl -= 1
        adapter_config_str += "}"
        return adapter_config_str

    def _get_write_data_string(self, participant: n.ParticipantNode, mesh: n.MeshNode) -> str:
        """
        Create a string of the form:
        "write_data_names": ["data1", "data2", ...],
        where the given participant writes the data to the given mesh.
        :param participant: The participant that writes the data.
        :param mesh: The mesh the data is written to.
        :return: A string of the form described above.
        """
        # Check if the mesh has any write-data
        if not any(mesh == write_data.mesh for write_data in participant.write_data):
            logger.debug(f"No write-data found for mesh {mesh.name} and participant {participant.name}.")
            return ""
        write_data_str: str = f"\"write_data_names\": [\n"
        write_data_names: str = ", ".join(f"\"{write_data.data.name}\"" for write_data in participant.write_data
                                          if write_data.mesh == mesh) + "\n"
        indent: str = " " * 2
        write_data_str += indent + write_data_names
        write_data_str += f"],\n"
        return write_data_str

    def _get_read_data_string(self, participant: n.ParticipantNode, mesh: n.MeshNode) -> str:
        """
        Create a string of the form:
        "read_data_names": ["data1", "data2", ...],
        where the given participant reads the data from the given mesh.
        :param participant: The participant that reads the data.
        :param mesh: The mesh the data is read from.
        :return: A string of the form described above.
        """
        # Check if the mesh has any read-data
        if not any(mesh == read_data.mesh for read_data in participant.read_data):
            logger.debug(f"No read-data found for mesh {mesh.name} and participant {participant.name}.")
            return ""
        read_data_str: str = f"\"read_data_names\": [\n"
        read_data_names: str = ", ".join(f"\"{read_data.data.name}\"" for read_data in participant.read_data
                                         if read_data.mesh == mesh) + "\n"
        indent: str = " " * 2
        read_data_str += indent + read_data_names
        read_data_str += f"],\n"
        return read_data_str

    def _get_patch_string(self, mesh: n.MeshNode, mesh_patch_map: dict[n.MeshNode, set[str]]) -> str:
        """
        Create a string of the form:
        "patches": ["patch1", "patch2", ...],
        where the given mesh uses the given patches, i.e., either reads data from or writes data to them.
        :param mesh: The mesh using the patches.
        :param mesh_patch_map: A dict mapping meshes to sets of patches.
        :return: A string of the form described above.
        """
        # This should never happen, but better check just i case
        if mesh not in mesh_patch_map:
            logger.error(f"Mesh {mesh.name} does not use any patches. This is likely an error within the program.")
            return ""
        patch_str: str = f"\"patches\": [\n"
        patch_names: str = ", ".join(f"\"{item}\"" for item in mesh_patch_map[mesh]) + "\n"
        indent: str = " " * 2
        patch_str += indent + patch_names
        patch_str += f"],\n"
        return patch_str

    def _create_adapter_config_file(self, participant: n.ParticipantNode,
                                    patch_map: dict[n.MeshNode, set[str]],
                                    directory: str = "./", filename: str = "adapter-config.json"):
        """
        Write an adapter-config.json file for the given participant to the given directory.
        :param participant: The participant for which the adapter-config.json file is created.
        :param patch_map: A dict mapping meshes to sets of patches.
        :param directory: The directory to save the file in.
        :param filename: The name of the file.
        """
        with open(directory + filename, "w") as f:
            f.write(self._create_adapter_config_str(participant, patch_map))
        logger.info(f"Adapter configuration file for participant {participant.name} written to {directory + filename}")

    def create_adapter_configs(self, parent_directory: str = "./"):
        """
        Create adapter-config.json files for all participants.
        The files are saved from the given parent-directory, in subdirectories of the form "participant-solver/".
        """
        for participant in self.participant_solver_map:
            logger.debug(f"Creating adapter configuration file for participant {participant.name}.")
            # Use lowercase
            directory: str = (parent_directory.lower() + participant.name.lower() + "-"
                              + self.participant_solver_map[participant].lower() + "/")
            self._create_adapter_config_file(participant, self.patch_map, directory=directory)
