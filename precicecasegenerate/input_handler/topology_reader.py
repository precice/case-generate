from ruamel.yaml import YAML
import json
import jsonschema
import logging
import re
from pathlib import Path
from importlib.resources import files
from precicecasegenerate import helper

logger = logging.getLogger(__name__)


class TopologyReader:
    """
    Read a given topology.yaml file and save it as a dict.
    """

    def __init__(self, path_to_topology_file: Path):
        # Convert to Path object just in case
        self.topology_file_path = Path(path_to_topology_file)
        self.topology = self._read_topology()

    def _read_topology(self) -> dict:
        """
        Read the topology file and convert it to a dict.
        :return: The topology dict.
        """
        logger.debug(f"Reading topology file at {self.topology_file_path.resolve()}")
        yaml = YAML(typ="safe")
        with open(self.topology_file_path, "r") as topology_file:
            topology = yaml.load(topology_file)
        return topology

    def get_topology(self) -> dict:
        """
        Return the topology dict.
        :return: A dict representing the topology.
        """
        return self.topology
