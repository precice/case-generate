from enum import Enum
from precice_config_graph import nodes as n
from precice_config_graph import enums as e

"""
Helper items and classes for the NodeCreator. 
"""
# Link to the precice/case-generate repository
case_generate_repository_url: str = "https://github.com/precice/case-generate"

# Set defaults here to be able to change them easily
DEFAULT_DATA_TYPE: e.DataType = e.DataType.SCALAR
DEFAULT_PARTICIPANT_DIMENSIONALITY: int = 3
DEFAULT_MAPPING_METHOD: e.MappingMethod = e.MappingMethod.NEAREST_NEIGHBOR
DEFAULT_ACCELERATION_TYPE: e.AccelerationType = e.AccelerationType.IQN_ILS
DEFAULT_M2N_TYPE: e.M2NType = e.M2NType.SOCKETS
DEFAULT_EXPLICIT_COUPLING_TYPE: e.CouplingSchemeType = e.CouplingSchemeType.PARALLEL_EXPLICIT
DEFAULT_IMPLICIT_COUPLING_TYPE: e.CouplingSchemeType = e.CouplingSchemeType.PARALLEL_IMPLICIT
DEFAULT_CONVERGENCE_MEASURE_TYPE: e.ConvergenceMeasureType = e.ConvergenceMeasureType.RELATIVE
DEFAULT_DATA_KIND: str = "intensive"
DEFAULT_MAPPING_KIND: str = "read"

EXTENSIVE_DATA: list[str] = ["force", "displacement"]
INTENSIVE_DATA: list[str] = ["temperature", "pressure", "velocity", "heat-flux", ]

# To make duplicate data names unique
DATA_UNIQUIFIERS: list[str] = [
    "magnificent",
    "grand",
    "wonderful",
    "suspicious",
    "mischievous",
    "clever",
    "pretty",
    "scary",
    "adventurous",
    "alien",
    "humungous",
    "informative",
]


def get_participant_solver_directory(parent_directory: str, participant_name: str, solver_name: str) -> str:
    """
    Return the name of the directory for a participant of the simulation.
    The adapter-config.json and run.sh files for this participant will be saved in this directory.
    :param parent_directory: The parent directory of the participant's directory.
    :param participant_name: The name of the participant.
    :param solver_name: The name of the solver.
    :return: A string representing the directory name.
    """
    # Append a / if needed
    parent_directory = parent_directory if parent_directory.endswith("/") else parent_directory + "/"
    return parent_directory.lower() + participant_name.lower() + "-" + solver_name.lower() + "/"


class PatchState(Enum):
    EXTENSIVE = "extensive"
    INTENSIVE = "intensive"


class PatchNode:
    """
    A class to represent a patch from a topology.yaml file.
    """

    def __init__(self, name: str, participant: n.ParticipantNode, mesh: n.MeshNode, label: PatchState):
        """
        Initialize a PatchNode.
        :param name: The name of the patch.
        :param participant: The participant that owns the patch.
        :param mesh: The mesh the patch is on.
        :param label:
        """
        self.name = name
        self.participant = participant
        self.mesh = mesh
        self.label = label
