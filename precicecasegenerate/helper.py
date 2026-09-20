import random
from enum import Enum
from pathlib import Path
from precice_config_graph import nodes as n
from precice_config_graph import enums as e

"""
Helper items and classes for the NodeCreator. 
"""
# Indent for config
INDENT: str = " " * 4

# Link to the precice/case-generate repository
case_generate_repository_url: str = "https://github.com/precice/case-generate"

# Set defaults here to be able to change them easily
DEFAULT_DATA_TYPE: e.DataType = e.DataType.VECTOR
DEFAULT_PARTICIPANT_DIMENSIONALITY: int = 3
DEFAULT_MAPPING_METHOD: e.MappingMethod = e.MappingMethod.NEAREST_NEIGHBOR
DEFAULT_ACCELERATION_TYPE: e.AccelerationType = e.AccelerationType.IQN_ILS
DEFAULT_M2N_TYPE: e.M2NType = e.M2NType.SOCKETS
DEFAULT_EXPLICIT_COUPLING_TYPE: e.CouplingSchemeType = e.CouplingSchemeType.PARALLEL_EXPLICIT
DEFAULT_IMPLICIT_COUPLING_TYPE: e.CouplingSchemeType = e.CouplingSchemeType.PARALLEL_IMPLICIT
DEFAULT_CONVERGENCE_MEASURE_TYPE: e.ConvergenceMeasureType = e.ConvergenceMeasureType.RELATIVE
DEFAULT_DATA_KIND: str = "intensive"
DEFAULT_MAPPING_KIND: str = "read"
DEFAULT_LOCATION_TYPE: str = "surface"

EXTENSIVE_DATA: list[str] = [
    "force",
    "heat-transfer",
    "heattransfer",
]

INTENSIVE_DATA: list[str] = [
    "displacement",
    "temperature",
    "pressure",
    "velocity",
    "heat-flux",
    "heatflux",
    "traction"
]


class DataKind(Enum):
    EXTENSIVE = "extensive"
    INTENSIVE = "intensive"


def get_data_label(data_name: str) -> DataKind:
    """
    Return the kind / label of data based on the name of the data:
    either "extensive" or "intensive"; with default DEFAULT_DATA_KIND.
    :param data_name: The name of the data.
    :return: Enum type of the data kind.
    """
    if _is_extensive(data_name):
        return DataKind.EXTENSIVE
    elif _is_intensive(data_name):
        return DataKind.INTENSIVE
    else:
        return DataKind(DEFAULT_DATA_KIND)


def is_unknown_data_kind(data_name: str) -> bool:
    """
    Checks if the given data name is associated with an unknown data kind, i.e., neither extensive nor intensive.
    :param data_name: The name of the data to check.
    :return: True, if the data kind is unknown. False otherwise.
    """
    return not _is_extensive(data_name) and not _is_intensive(data_name)


def _is_extensive(data_name: str) -> bool:
    """
    Checks if the given data name is associated with an extensive data.
    :param data_name: The name of the data to check.
    :return: True, if the data extensive. False otherwise.
    """
    return any(data_name.lower().__contains__(extensive_data) for extensive_data in EXTENSIVE_DATA)


def _is_intensive(data_name: str) -> bool:
    """
    Checks if the given data name is associated with an intensive data.
    :param data_name: The name of the data to check.
    :return: True, if the data intensive. False otherwise.
    """
    return any(data_name.lower().__contains__(intensive_data) for intensive_data in INTENSIVE_DATA)


# To make duplicate data names unique
DATA_UNIQUIFIERS: list[str] = [
    "adventurous",
    "alien",
    "grand",
    "humungous",
    "informative",
    "magnificent",
    "mischievous",
    "pretty",
    "scary",
    "suspicious",
    "wonderful",
]

# A default data type if none is given
DEFAULT_DATA_TYPES: dict[str, e.DataType] = {
    "force": e.DataType.VECTOR,
    "displacement": e.DataType.VECTOR,
    "temperature": e.DataType.SCALAR,
    "pressure": e.DataType.SCALAR,
    "velocity": e.DataType.VECTOR,
    "heat-flux": e.DataType.VECTOR,
    "heatflux": e.DataType.VECTOR,
    "heat-transfer": e.DataType.SCALAR,
    "heattransfer": e.DataType.SCALAR,
}


def capitalize_name(name: str) -> str:
    """
    Capitalize the first letter of each word in a string.
    :param name: The string to capitalize.
    :return: A capitalized string.
    """
    return "-".join(part[:1].upper() + part[1:] for part in name.split("-"))


def get_uniquifier() -> str:
    """
    Return a random string from the DATA_UNIQUIFIERS list and remove it from the list.
    :return: A string to be used as a unique identifier for data names.
    """
    unique_number = random.randint(0, len(DATA_UNIQUIFIERS) - 1)
    return DATA_UNIQUIFIERS.pop(unique_number)


def get_participant_solver_directory(parent_directory: Path, participant_name: str, solver_name: str) -> Path:
    """
    Return the name of the directory for a participant of the simulation.
    The adapter-config.json and run.sh files for this participant will be saved in this directory.
    :param parent_directory: The parent directory of the participant's directory.
    :param participant_name: The name of the participant.
    :param solver_name: The name of the solver.
    :return: A Path representing the directory name.
    """
    participant_directory: Path = parent_directory / (participant_name.lower() + "-" + solver_name.lower())
    return participant_directory


class LocationType(Enum):
    """
    Type of a location in the topology.yaml file.
    The type can be either surface or volume.
    """
    SURFACE = "surface"
    VOLUME = "volume"


class LocationNode:
    """
    A class to represent a location from a topology.yaml file.
    """

    def __init__(self, name: str, participant: n.ParticipantNode,
                 meshes: dict[n.ParticipantNode, dict[DataKind, n.MeshNode]],
                 type: LocationType = LocationType(DEFAULT_LOCATION_TYPE)):
        """
        Initialize a LocationNode.
        :param name: The name of the location.
        :param participant: The participant that owns the location.
        :param meshes: A dict mapping participants to meshes.
        More accurately, the participants are the target participants of the location
        and the meshes are the ones used by the owning participant in communication with the target participant.
        As the mesh must be either "extensive" or "intensive", the target participant maps to a dict of meshes
        with the keys "extensive" and "intensive".
        :param type: The type of the location (surface or volume). Defaults to surface.
        """
        self.name = name
        self.participant = participant
        self.meshes = meshes
        self.type = type

    def __eq__(self, other):
        """
        Equality check for LocationNode objects.
        Two LocationNode objects are equal if they have the same name, participant, label and type.
        As the mesh is assigned later, it is ignored for equality checks.
        :param self: The current LocationNode object.
        :param other: The other LocationNode object to compare with.
        :return: True if the objects are equal, False otherwise.
        """
        if not isinstance(other, LocationNode):
            return False
        return (self.name == other.name and
                self.participant == other.participant and
                self.type == other.type)

    def __hash__(self):
        return hash((self.name, self.participant, self.type))
