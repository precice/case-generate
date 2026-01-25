import json
import jsonschema
import logging
from pathlib import Path
from importlib.resources import files

from precice_config_graph import nodes as n

import precicecasegenerate.helper as helper

logger = logging.getLogger(__name__)


class AdapterConfigCreator:
    """
    A class that handles creating adapter configuration files for participants in the correct directory.
    """

    def __init__(self, participant_solver_map: dict[n.ParticipantNode, str],
                 mesh_patch_map: dict[n.MeshNode, set[str]], precice_config_filename: str = "precice-config.xml"):
        """
        Initialize an AdapterConfigCreator object, which creates adapter configuration files for each participant.
        :param participant_solver_map: A dict mapping participant nodes to their solver names.
        :param mesh_patch_map: A map mapping meshes to sets of patches.
        :param precice_config_filename: The name of the precice-config.xml file.
        """
        self.participant_solver_map = participant_solver_map
        self.patch_map = mesh_patch_map
        self.precice_config_filename = precice_config_filename

    def _create_adapter_config_dict(self, participant: n.ParticipantNode,
                                    mesh_patch_map: dict[n.MeshNode, set[str]]) -> dict[str, str | list[str]]:
        """
        Create a dictionary representing the adapter configuration file for the given participant.
        :param participant: The participant for which the adapter configuration is created.
        :param mesh_patch_map: A map mapping meshes to sets of patches that they use.
        :return: A dict representing the adapter configuration file for the given participant.
        """
        interfaces: list[dict[str, str | list[str]]] = []

        # Create an entry for each mesh
        for mesh in participant.provide_meshes:
            # Get the patches used by the current mesh
            patches: list[str] = sorted(list(mesh_patch_map.get(mesh, [])))

            # Get the read-data of the participant and the current mesh
            read_data: list[str] = [
                rd.data.name for rd in participant.read_data
                if rd.mesh == mesh
            ]

            # Get the write-data of the participant and the current mesh
            write_data: list[str] = [
                wd.data.name for wd in participant.write_data
                if wd.mesh == mesh
            ]

            # The mesh entry is a dictionary containing the mesh name and the patches used by it
            mesh_entry: dict[str, str | list[str]] = {
                "mesh_name": mesh.name,
                "patches": patches
            }

            # Only add read-/write-data keys if the mesh reads/writes data
            if read_data:
                mesh_entry["read_data_names"] = sorted(read_data)
            if write_data:
                mesh_entry["write_data_names"] = sorted(write_data)

            # Add the mesh entry to the list of interfaces
            interfaces.append(mesh_entry)
            logger.debug(f"Created adapter configuration entry for mesh {mesh.name} "
                         f"in participant {participant.name}'s adapter-config.")

        # The adapter-config file is a dictionary containing the participant name,
        # the path to the precice-config.xml file and the list of interfaces
        return {
            "participant_name": participant.name,
            "precice_config_file_name": f"../{self.precice_config_filename}",
            "interfaces": interfaces
        }

    def _validate_adapter_config_file(self, directory: Path = "./", filename: str = "adapter-config.json"):
        """
        Validate the adapter-config.json file in the given directory against the schema.
        :param directory: The directory containing the adapter-config.json file.
        :param filename: The name of the adapter-config file.
        :return: None
        """
        # Convert to Path object just in case
        directory = Path(directory)
        schema_path = files("precicecasegenerate.schemas") / "adapter-config-schema.json"
        file_path: Path = directory / filename

        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        with open(file_path, "r") as f:
            adapter_config = json.load(f)

        try:
            jsonschema.validate(adapter_config, schema)
            logger.debug(f"Adapter config file {file_path} adheres to the schema.")
        except jsonschema.ValidationError as e:
            logger.error(f"Adapter config file {file_path} does not adhere to the schema "
                         f"as specified in {schema_path}: {e.message}. This is likely an error within the program.")

    def _create_adapter_config_file(self, participant: n.ParticipantNode,
                                    patch_map: dict[n.MeshNode, set[str]],
                                    directory: Path = "./", filename: str = "adapter-config.json"):
        """
        Write an adapter-config.json file for the given participant to the given directory.
        :param participant: The participant for which the adapter-config.json file is created.
        :param patch_map: A dict mapping meshes to sets of patches.
        :param directory: The directory to save the file in.
        :param filename: The name of the file.
        """
        # Convert to Path object just in case
        directory = Path(directory)
        file_path: Path = directory / filename
        adapter_config: dict[str, str | list[str]] = self._create_adapter_config_dict(participant, patch_map)
        with open(file_path, "w") as f:
            json.dump(adapter_config, f, indent=4)
        logger.info(f"Adapter configuration file for participant {participant.name} written to {file_path}")

    def create_adapter_configs(self, parent_directory: Path = "./"):
        """
        Create adapter-config.json files for all participants and directly validate them afterwards.
        The files are saved from the given parent-directory, in subdirectories of the form "participant-solver/".
        """
        # Convert to Path object just in case
        parent_directory = Path(parent_directory)
        for participant in self.participant_solver_map:
            logger.debug(f"Creating adapter configuration file for participant {participant.name}.")
            directory: Path = helper.get_participant_solver_directory(parent_directory, participant.name,
                                                                      self.participant_solver_map[participant])
            self._create_adapter_config_file(participant, self.patch_map, directory=directory)
            self._validate_adapter_config_file(directory=directory)
