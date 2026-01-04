from precice_config_graph import enums as e

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

EXTENSIVE_DATA: list[str] = ["force"]
INTENSIVE_DATA: list[str] = ["temperature", "pressure", "velocity", "heat-flux", "displacement"]

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
