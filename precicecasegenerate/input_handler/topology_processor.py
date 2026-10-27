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
        self._preprocess_data()

        return return_value

    def _preprocess_data(self):
        """
        Preprocess data entries in the topology. This includes the ``data: ...`` and ``data-type: ...`` entries.
        First, the data-types are written to the topology for each exchange, i.e., the default is appended
        if no value is present.
        Next, the data are renamed if they appear with different types.
        Finally, data is uniquified if it appears in exchanges between the same two participants in both directions.
        :return: None
        """
        # First, apply a data-type to each exchange and output a warning if none was given
        # Keep track of data that we have seen that did not have a data type.
        seen_data_no_type: set[str] = set()
        for exchange in self.topology["exchanges"]:
            data_name: str = exchange["data"]
            data_type: str | None = exchange.get("data-type")
            if data_type is None:
                data_type = helper.DEFAULT_DATA_TYPE.value
                normalized_data_name: str = helper.normalize_data_name(data_name)
                # Check if the data has a default type. Sort by key length to have a deterministic order
                for key in sorted(helper.DEFAULT_DATA_TYPES.keys(), key=len, reverse=True):
                    if key in normalized_data_name:
                        data_type = helper.DEFAULT_DATA_TYPES[key].value
                        break

                if data_name not in seen_data_no_type:
                    logger.warning(f"No data type provided for data \"{data_name}\". "
                                   f"Choosing default type \"{data_type}\".")
                seen_data_no_type.add(data_name)
                exchange["data-type"] = data_type
                logger.debug(f"Added default data-type \"{data_type}\" for data \"{data_name}\".")

        # Second, check which data has multiple types
        # Keep track of the types
        data_data_type_map: dict[str, set[str]] = {}
        for exchange in self.topology["exchanges"]:
            data_name: str = exchange["data"]
            data_type: str = exchange["data-type"]
            if data_name in data_data_type_map:
                data_data_type_map[data_name].add(data_type)
            else:
                data_data_type_map[data_name] = {data_type}
        # Now go over each exchange again and split the data into -scalar or -vector variants
        for exchange in self.topology["exchanges"]:
            data_name: str = exchange["data"]
            data_type: str = exchange["data-type"]
            # Check if the data has multiple types. If so, we need to split it
            if len(data_data_type_map[data_name]) > 1:
                exchange["data"] = data_name + "-" + data_type.capitalize()
        # Log messages
        for data_name in data_data_type_map.keys():
            if len(data_data_type_map[data_name]) > 1:
                logger.warning(f"Split data \"{data_name}\" into \"{data_name}-Scalar\" "
                               f"and \"{data_name}-Vector\".")

        # Third, uniquify data names if they appear in exchanges of the form A--X->B and B--X->A
        # Map data -> tuples of (from-participant, to_participant)
        data_exchange_map: dict[str, set[tuple[str, str]]] = {}
        for exchange in self.topology["exchanges"]:
            data_name: str = exchange["data"]
            from_participant: str = exchange["from"]
            to_participant: str = exchange["to"]
            if data_name in data_exchange_map:
                data_exchange_map[data_name].add((from_participant, to_participant))
            else:
                data_exchange_map[data_name] = {(from_participant, to_participant)}

        # Keep track of which data we uniquifed, map data, from-participant, to-participant -> uniquified_data_name
        data_uniquified_data_map: dict[tuple[str, str, str], str] = {}
        for exchange in self.topology["exchanges"]:
            data_name: str = exchange["data"]
            from_participant: str = exchange["from"]
            to_participant: str = exchange["to"]
            if ((from_participant, to_participant) in data_exchange_map[data_name]
                    and (to_participant, from_participant) in data_exchange_map[data_name]):
                # Create a new data name for the pair (from-participant,to-participant) and store it
                new_data_name = helper.get_uniquifier().capitalize() + "-" + data_name
                data_uniquified_data_map[(from_participant, to_participant, data_name)] = new_data_name
                logger.warning(f"Data name \"{data_name}\" is exchanged by participants {from_participant} "
                               f"and {to_participant} in both directions. Using \"{new_data_name}\" for one direction.")
                # Remove the pair so that we do not create more new data for the pair
                data_exchange_map[data_name].remove((from_participant, to_participant))

        # Now actually rename the data
        for exchange in self.topology["exchanges"]:
            data_name: str = exchange["data"]
            from_participant: str = exchange["from"]
            to_participant: str = exchange["to"]
            if (from_participant, to_participant, data_name) in data_uniquified_data_map:
                exchange["data"] = data_uniquified_data_map[(from_participant, to_participant, data_name)]

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

    def _format_participant_names(self):
        """
        This method works in-place with the topology dict.
        Participant names are capitalized, any spaces and other special characters are removed.
        Additionally, the participant names are updated in the exchanges to match the new names.
        :return: None
        """
        participant_name_map: dict[str, str] = {}
        for participant in self.topology["participants"]:
            name: str = participant["name"]
            new_name: str = name
            no_special_symbols_name: str = re.sub(r"[^a-zA-Z0-9]", "", new_name)
            if not name[0].isupper():
                new_name = new_name[0] + new_name[1:]
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
            from_location_names: list[str] = exchange["from-location-names"]
            to_location_names: list[str] = exchange["to-location-names"]

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
