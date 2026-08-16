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

    def validate_topology(self) -> int:
        """
        Check if the topology adheres to the defined schema in schemas/topology-schema.json
        :return: 0 if the topology is valid, 1 otherwise
        """
        schema_path = files("precicecasegenerate.schemas") / "topology-schema.json"

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(self.topology, schema)
            logger.debug("Topology file adheres to the schema.")
        except jsonschema.ValidationError as e:
            logger.critical(f"Topology file {self.topology_file_path.resolve()} does not adhere to the schema "
                            f"as specified in {schema_path}: {e.message}. Aborting program.")
            return 1
        return 0

    def check_topology(self) -> int:
        """
        Check if the topology is valid and update it if necessary.
        It is checked whether:

        - participant names are unique.
        - exchanges only contain known "to" and "from" participants.
        - exchanges are unique, when ignoring "to-location-name", "from-location-name" and "type" tags.
        - locations of the same participant are not defined with different "location-type" tags. If a location has its type defined only once, the type is written to the topology in all other exchanges where it was not defined.

        If any of these checks fail, an error message is printed and the program is aborted.
        Additionally, it is checked if any of the data names contains one of the uniquifiers defined in
        helper.DATA_UNIQUIFIERS. If so, this uniquifier is removed from the list of uniquifiers (this does not cause
        an error).
        :return: 0 if topology is valid, 1 otherwise
        """
        participant_names: set[str] = set()
        # Check if participant names are unique
        for participant in self.topology["participants"]:
            if participant["name"] in participant_names:
                logger.critical(
                    f"Duplicate participant name {participant['name']} in topology file {self.topology_file_path}.")
                return 1
            participant_names.add(participant["name"])
        logger.debug("Topology does not contain duplicate participant names.")

        # Check if participants actually appear in exchanges
        participants_in_exchanges: set[str] = set()
        # Check if exchanges are unique
        known_exchanges: set[tuple[str, str, str]] = set()
        # Check if locations of a participant have only one type
        participant_location_type_map: dict[tuple[str, str], str] = {}

        # Check if exchanges only contain known "to" and "from" participants
        for exchange in self.topology["exchanges"]:
            to_participant: str = exchange["to"]
            from_participant: str = exchange["from"]
            data: str = exchange["data"]
            from_location_name: str = exchange["from-location-name"]
            to_location_name: str = exchange["to-location-name"]
            from_location_type: str = exchange.get("from-location-type")
            to_location_type: str = exchange.get("to-location-type")

            participants_in_exchanges.add(to_participant)
            participants_in_exchanges.add(from_participant)

            if to_participant not in participant_names:
                logger.critical(f"Unknown participant {to_participant} in topology file "
                                f"{self.topology_file_path}.")
                return 1
            if from_participant not in participant_names:
                logger.critical(f"Unknown participant {from_participant} in topology file "
                                f"{self.topology_file_path}.")
                return 1

            if from_participant == to_participant:
                logger.critical(f"Participant {from_participant} exchanges {data} with itself.")
                return 1

            # Check if the exchanges are unique when ignoring certain attributes
            exchange_info: tuple[str, str, str] = (to_participant.lower(), from_participant.lower(), data.lower())
            if exchange_info in known_exchanges:
                logger.critical(f"Duplicate exchange from {from_participant} to {to_participant} for data {data}.")
                return 1
            known_exchanges.add(exchange_info)

            # Gather the location types of the locations of the participant only if they were defined in the topology
            # and check if they are unique
            if from_location_type is not None:
                from_location: tuple[str, str] = (from_participant, from_location_name)
                if from_location in participant_location_type_map and participant_location_type_map[
                    from_location] != from_location_type:
                    logger.critical(f"Participant {from_participant} has multiple location types for location "
                                    f"{from_location_name}.")
                    return 1
                participant_location_type_map[from_location] = from_location_type
            if to_location_type is not None:
                to_location: tuple[str, str] = (to_participant, to_location_name)
                if to_location in participant_location_type_map and participant_location_type_map[
                    to_location] != to_location_type:
                    logger.critical(f"Participant {to_participant} has multiple location types for location "
                                    f"{to_location_name}.")
                    return 1
                participant_location_type_map[to_location] = to_location_type

            # Remove uniquifiers from the list if they are present in a data name
            for uniquifier in helper.DATA_UNIQUIFIERS.copy():
                if uniquifier in data:
                    helper.DATA_UNIQUIFIERS.remove(uniquifier)
                    logger.debug(f"Removed uniquifier {uniquifier} from the list of uniquifiers.")

        for participant in self.topology["participants"]:
            if participant["name"] not in participants_in_exchanges:
                logger.warning(f"Removing participant {participant['name']} as it is defined but never used.")
                self.topology["participants"].remove(participant)

        # Now we are guaranteed that all participants locations have the same type.
        # We can now write this back into the topology to make further processing easier.
        for exchange in self.topology["exchanges"]:
            from_participant: str = exchange["from"]
            to_participant: str = exchange["to"]
            from_location_name: str = exchange["from-location-name"]
            to_location_name: str = exchange["to-location-name"]
            # There is a maximum of one location type for each participant defined in the topology,
            # so we can just take it or use the default location type if it is not defined in the topology.
            exchange["from-location-type"] = participant_location_type_map.get((from_participant, from_location_name),
                                                                               helper.DEFAULT_LOCATION_TYPE)
            exchange["to-location-type"] = participant_location_type_map.get((to_participant, to_location_name),
                                                                             helper.DEFAULT_LOCATION_TYPE)
        logger.debug("Topology does not contain any errors.")
        return 0

    def preprocess_participant_names(self):
        """
        This method works in-place with the topology dict.
        Participant names are capitalized, any spaces are replaced by hyphens, and other special characters are removed.
        Additionally, the participant names are updated in the exchanges to match the new names.
        :return: None
        """
        participant_name_map: dict[str, str] = {}
        for participant in self.topology["participants"]:
            name: str = participant["name"]
            new_name: str = name
            no_special_symbols_name: str = re.sub(r"[^a-zA-Z0-9\-]", "", new_name)
            if not name[0].isupper():
                new_name = new_name.capitalize()
            if " " in name:
                new_name = new_name.replace(" ", "-")
            if no_special_symbols_name != new_name:
                new_name = no_special_symbols_name
            if name != new_name:
                logger.warning(f"Participant name {name} was updated to {new_name} to adhere to naming convention.")
            # Save the reference old name -> new name
            participant_name_map[name] = new_name
            # Update the name in the topology
            participant["name"] = new_name

        # Update the names in the exchanges to match the new names
        for exchange in self.topology["exchanges"]:
            exchange["to"] = participant_name_map[exchange["to"]]
            exchange["from"] = participant_name_map[exchange["from"]]

    def get_topology(self) -> dict:
        """
        Return the topology dict.
        :return: A dict representing the topology.
        """
        return self.topology
