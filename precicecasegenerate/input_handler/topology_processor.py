import json
import jsonschema
import logging
import re
from pathlib import Path
from importlib.resources import files
from precicecasegenerate import helper

logger = logging.getLogger(__name__)


class TopologyProcessor:

    def __init__(self, topology: dict, topology_file_path: Path):
        """
        Initialize the TopologyProcessor.
        :param topology: The topology to be preprocessed.
        :param topology_file_path: The path to the topology file.
        """
        self.topology = topology
        self.topology_file_path = topology_file_path

        # State used across methods
        self._participant_location_type_map: dict[tuple[str, str], helper.LocationType] = {}

    def process(self) -> int:
        """
        Call all validation and preprocessing methods and return the result.
        This method updates the topology dict in-place.
        :return: 0, if the topology is valid, 1 otherwise
        """
        return_value: int = self._validate_topology()
        if return_value != 0:
            return return_value


        return_value = self._validate_participants()
        if return_value != 0:
            return return_value

        return_value = self._validate_exchanges()
        if return_value != 0:
            return return_value

        self._format_participant_names()
        self._convert_lists_to_tuples()
        self._resolve_location_types()
        self._update_data_uniquifiers()
        self._remove_unused_participants()

        return return_value

    def _validate_topology(self) -> int:
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
        - exchanges are unique, when ignoring "type" tags.
        - locations of the same participant are not defined with different "location-type" tags. If a location has its type defined only once, the type is written to the topology in all other exchanges where it was not defined.

        If any of these checks fail, an error message is printed and the program is aborted.
        Additionally, it is checked if any of the data names contains one of the uniquifiers defined in
        helper.DATA_UNIQUIFIERS. If so, this uniquifier is removed from the list of uniquifiers (this does not cause
        an error).
        :return: 0 if topology is valid, 1 otherwise
        """
        participant_names: set[str] = set()
        # Check if participant names are unique
        # for participant in self.topology["participants"]:
        #     if participant["name"] in participant_names:
        #         logger.critical(
        #             f"Duplicate participant name {participant['name']} in topology file {self.topology_file_path}.")
        #         return 1
        #     participant_names.add(participant["name"])
        # logger.debug("Topology does not contain duplicate participant names.")

        # Check if participants actually appear in exchanges
        participants_in_exchanges: set[str] = set()
        # Check if exchanges are unique
        known_exchanges: set[tuple[str, str, str, str, str]] = set()
        # Check if locations of a participant have only one type
        participant_location_type_map: dict[tuple[str, str], helper.LocationType] = {}

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
            # exchange_info: tuple[str, str, str, str, str] = (to_participant.lower(), from_participant.lower(),
            #                                                  data.lower(),
            #                                                  from_location_name.lower(), to_location_name.lower())
            # if exchange_info in known_exchanges:
            #     logger.critical(f"Duplicate exchange from {from_participant} to {to_participant} for data {data}.")
            #     return 1
            # known_exchanges.add(exchange_info)

            # Gather the location types of the locations of the participant only if they were defined in the topology
            # and check if they are unique
            if from_location_type is not None:
                from_location: tuple[str, str] = (from_participant, from_location_name)
                if from_location in participant_location_type_map and participant_location_type_map[
                    from_location] != helper.LocationType(from_location_type):
                    logger.critical(f"Participant {from_participant} has multiple location-types for location "
                                    f"{from_location_name}.")
                    return 1
                participant_location_type_map[from_location] = helper.LocationType(from_location_type)
            if to_location_type is not None:
                to_location: tuple[str, str] = (to_participant, to_location_name)
                if to_location in participant_location_type_map and participant_location_type_map[
                    to_location] != helper.LocationType(to_location_type):
                    logger.critical(f"Participant {to_participant} has multiple location types for location "
                                    f"{to_location_name}.")
                    return 1
                participant_location_type_map[to_location] = helper.LocationType(to_location_type)

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
                                                                               helper.LocationType(
                                                                                   helper.DEFAULT_LOCATION_TYPE))
            exchange["to-location-type"] = participant_location_type_map.get((to_participant, to_location_name),
                                                                             helper.LocationType(
                                                                                 helper.DEFAULT_LOCATION_TYPE))

        # Convert the list into a tuple to make it hashable
        for exchange in self.topology["exchanges"]:
            exchange["from-location-names"] = tuple(exchange["from-location-names"])
            exchange["to-location-names"] = tuple(exchange["to-location-names"])

        logger.debug("Topology does not contain any errors.")
        return 0

    def _format_participant_names(self):
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

    def _convert_lists_to_tuples(self):
        """
        Convert location lists to tuples to make exchange dictionaries hashable later.
        """
        for exchange in self.topology["exchanges"]:
            if isinstance(exchange.get("from-location-names"), list):
                exchange["from-location-names"] = tuple(exchange["from-location-names"])
            if isinstance(exchange.get("to-location-names"), list):
                exchange["to-location-names"] = tuple(exchange["to-location-names"])

    def _validate_participants(self) -> int:
        """
        Ensure that all participant names are unique.
        """
        participant_names: set[str] = set()
        for participant in self.topology["participants"]:
            if participant["name"] in participant_names:
                logger.critical(
                    f"Duplicate participant name {participant['name']} in topology file {self.topology_file_path}.")
                return 1
            participant_names.add(participant["name"])
        return 0

    def _validate_exchanges(self) -> int:
        """
        Ensure that exchanges use valid participants, participants do not self-exchange, and have consistent location types.
        """
        participant_names = {p["name"] for p in self.topology["participants"]}

        known_exchanges: set[tuple[str, str, str, str, str]] = set()

        for exchange in self.topology["exchanges"]:
            to_participant: str = exchange["to"]
            from_participant: str = exchange["from"]
            data: str = exchange["data"]
            data_type: str = exchange.get("data-type", helper.DEFAULT_DATA_TYPE.value)
            exchange_type: str = exchange["type"]
            from_location_names: tuple[str] = exchange["from-location-names"]
            to_location_names: tuple[str] = exchange["to-location-names"]
            from_location_type: str = exchange.get("from-location-type")
            to_location_type: str = exchange.get("to-location-type")

            exchange_info: tuple[str, str, str, str, str] = (from_participant.lower(), to_participant.lower(),
                                                             data.lower(), data_type.lower(), exchange_type.lower())

            if exchange_info in known_exchanges:
                logger.critical(
                    f"Duplicate exchange detected: {from_participant} -> {to_participant} for data '{data}'. "
                    f"Please group multiple locations into a single list instead of creating multiple exchanges."
                )
                return 1

            known_exchanges.add(exchange_info)

            if to_participant not in participant_names:
                logger.critical(f"Unknown participant {to_participant} in topology file {self.topology_file_path}.")
                return 1
            if from_participant not in participant_names:
                logger.critical(f"Unknown participant {from_participant} in topology file {self.topology_file_path}.")
                return 1
            if from_participant == to_participant:
                logger.critical(f"Participant {from_participant} exchanges {data} with itself.")
                return 1

            if from_location_type is not None:
                for location in from_location_names:
                    key = (from_participant, location)
                    if key in self._participant_location_type_map and self._participant_location_type_map[
                        key] != helper.LocationType(from_location_type):
                        logger.critical(
                            f"Participant {from_participant} has multiple location-types for location {location}.")
                        return 1
                    self._participant_location_type_map[key] = helper.LocationType(from_location_type)

            if to_location_type is not None:
                for location in to_location_names:
                    key = (to_participant, location)
                    if key in self._participant_location_type_map and self._participant_location_type_map[
                        key] != helper.LocationType(to_location_type):
                        logger.critical(
                            f"Participant {to_participant} has multiple location types for location {location}.")
                        return 1
                    self._participant_location_type_map[key] = helper.LocationType(to_location_type)

        return 0

    def _resolve_location_types(self):
        """
        This method works in-place with the topology dict.
        Write missing location types back into the topology using the validated map.
        Has to be called after _validate_exchanges().
        """
        for exchange in self.topology["exchanges"]:
            from_participant: str = exchange["from"]
            to_participant: str = exchange["to"]
            from_location_names: tuple[str, ...] = exchange["from-location-names"]
            to_location_names: tuple[str, ...] = exchange["to-location-names"]

            exchange["from-location-type"] = self._participant_location_type_map.get(
                (from_participant, from_location_names[0]), helper.LocationType(helper.DEFAULT_LOCATION_TYPE))
            exchange["to-location-type"] = self._participant_location_type_map.get(
                (to_participant, to_location_names[0]), helper.LocationType(helper.DEFAULT_LOCATION_TYPE))

    def _update_data_uniquifiers(self):
        """
        Remove used uniquifiers from the global helper list.
        """
        for exchange in self.topology["exchanges"]:
            data = exchange["data"]
            for uniquifier in helper.DATA_UNIQUIFIERS.copy():
                if uniquifier in data:
                    helper.DATA_UNIQUIFIERS.remove(uniquifier)
                    logger.debug(f"Removed uniquifier {uniquifier} from the list of uniquifiers.")

    def _remove_unused_participants(self):
        """
        This method works in-place with the topology dict.
        Remove participants from the topology if they are not involved in any exchanges.
        """
        participants_in_exchanges: set[str] = set()
        for exchange in self.topology["exchanges"]:
            participants_in_exchanges.add(exchange["to"])
            participants_in_exchanges.add(exchange["from"])

        active_participants = []
        for participant in self.topology["participants"]:
            if participant["name"] not in participants_in_exchanges:
                logger.warning(f"Removing participant {participant['name']} as it is defined but never used.")
            else:
                active_participants.append(participant)

        self.topology["participants"] = active_participants
