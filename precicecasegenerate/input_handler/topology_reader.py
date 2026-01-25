import sys
import yaml
import json
import jsonschema
import logging
from importlib.resources import files
from precicecasegenerate import helper

logger = logging.getLogger(__name__)


class TopologyReader:
    """
    Read a given topology.yaml file and save it as a dict.
    """

    def __init__(self, path_to_topology_file: str):
        self.topology_file_path = path_to_topology_file
        self.topology = self._read_topology()
        self._validate_topology()
        self._check_topology()

    def _read_topology(self) -> dict:
        """
        Read the topology file and convert it to a dict.
        :return: The topology dict.
        """
        logger.debug(f"Reading topology file at {self.topology_file_path}")
        with open(self.topology_file_path, "r") as topology_file:
            topology = yaml.safe_load(topology_file)
        return topology

    def _validate_topology(self) -> None:
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

    def _check_topology(self) -> None:
        """
        Check if the topology is valid.
        This check includes:
        - Checking if participant names are unique.
        - Checking if exchanges only contain known "to" and "from" participants.
        - Checking if exchanges are unique, when ignoring "to-patch", "from-patch" and "type" tags.
        If any of these checks fail, an error message is printed and the program is aborted.
        Additionally, it is checked if any of the data names contains one of the uniquifiers defined in
        helper.DATA_UNIQUIFIERS. If so, this uniquifier is removed from the list of uniquifiers.
        """
        participant_names: set[str] = set()
        # Check if participant names are unique
        for participant in self.topology["participants"]:
            if participant["name"] in participant_names:
                logger.critical(
                    f"Duplicate participant name {participant['name']} in topology file {self.topology_file_path}.")
                sys.exit(1)
            participant_names.add(participant["name"])
        logger.debug("Topology does not contain duplicate participant names.")

        exchanges: list[dict] = []
        # Check if exchanges only contain known "to" and "from" participants
        # Check if exchanges are unique, when ignoring "to-patch", "from-patch" and "type" tags
        for exchange in self.topology["exchanges"]:
            to_participant: str = exchange["to"]
            from_participant: str = exchange["from"]
            if to_participant not in participant_names:
                logger.critical(f"Unknown participant {to_participant} in topology file "
                                f"{self.topology_file_path}.")
                sys.exit(1)
            if from_participant not in participant_names:
                logger.critical(f"Unknown participant {from_participant} in topology file "
                                f"{self.topology_file_path}.")
                sys.exit(1)
            data: str = exchange["data"]
            data_type: str = exchange.get("type", None)
            # Remove uniquifiers from the list if they are present in a data name
            for uniquifier in helper.DATA_UNIQUIFIERS.copy():
                if uniquifier in data:
                    helper.DATA_UNIQUIFIERS.remove(uniquifier)
                    logger.debug(f"Removed uniquifier {uniquifier} from the list of uniquifiers.")
            unique_exchange: dict[str, str] = {"to": to_participant, "from": from_participant, "data": data,
                                               "data-type": data_type}
            if unique_exchange in exchanges:
                logger.critical(f"Duplicate exchange {unique_exchange} in topology file {self.topology_file_path}.")
                sys.exit(1)
            exchanges.append(unique_exchange)

        logger.debug("Topology does not contain any errors.")

    def get_topology(self) -> dict:
        """
        Return the topology dict.
        :return: A dict representing the topology.
        """
        return self.topology
