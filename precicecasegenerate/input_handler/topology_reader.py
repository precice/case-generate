import sys
import yaml
import json
import jsonschema
import logging
from importlib.resources import files

logger = logging.getLogger(__name__)


class TopologyReader:
    """
    Read a given topology.yaml file and save it as a config graph (?)
    """

    def __init__(self, path_to_topology_file: str):
        self.topology_file_path = path_to_topology_file
        self.topology = self._read_topology()
        self._check_topology()

    def _read_topology(self) -> dict:
        """
        Read the topology file and convert it to a dict.
        This dict is saved as an attribute of the TopologyReader object.
        :return: None
        """
        logger.debug(f"Reading topology file at {self.topology_file_path}")
        with open(self.topology_file_path, "r") as topology_file:
            topology = yaml.safe_load(topology_file)
        return topology

    def _check_topology(self) -> None:
        """
        Check if the topology adheres to the defined schema in schemas/topology-schema.json
        """
        schema_path = files("precicecasegenerate.schemas") / "topology-schema.json"

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(self.topology, schema)
            logger.debug("Topology file adheres to the schema.")
        except jsonschema.ValidationError as e:
            logger.critical(f"Topology file {self.topology_file_path} does not adhere to the schema "
                            f"as specified in {schema_path}: {e.message}. Aborting program.")
            sys.exit(1)

    def get_topology(self) -> dict:
        """
        Return the topology dict.
        :return: A dict representing the topology.
        """
        return self.topology
