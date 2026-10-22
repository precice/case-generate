import logging

from precice_config_graph import nodes as n
from precice_config_graph import enums as e
import precicecasegenerate.helper as helper

logger = logging.getLogger(__name__)


class NodeCreator:

    def __init__(self, topology: dict):
        """
        Initialize the NodeCreator.
        This method automatically creates all nodes from the topology.
        :param topology: The topology to be used for creating the nodes.
        """
        self.topology = topology
        # Nodes to be created
        self.participants: list[n.ParticipantNode] = []
        self.data: list[n.DataNode] = []
        self.meshes: list[n.MeshNode] = []
        self.coupling_schemes: list[n.CouplingSchemeNode | n.MultiCouplingSchemeNode] = []
        self.m2ns: list[n.M2NNode] = []
        # Location nodes are important for adapter configs
        self.locations: list[helper.LocationNode] = []

        # Containers for temporary values
        # Dimensionality is needed for meshes
        self.participant_dimensionality: dict[n.ParticipantNode, int] = {}
        self.exchange_types: dict[n.ExchangeNode, str] = {}

        self._create_nodes()

    def get_mesh_location_map(self) -> dict[n.MeshNode, set[helper.LocationNode]]:
        """
        Create a dict mapping mesh nodes to sets of locations that they use / contain.
        :return: A dict mapping mesh nodes to sets of location nodes.
        """
        mesh_location_map: dict[n.MeshNode, set[helper.LocationNode]] = {}
        for location in self.locations:
            for kind_dict in location.meshes.values():
                for mesh in kind_dict.values():

                    # Create a a new entry if necessary
                    if mesh not in mesh_location_map:
                        mesh_location_map[mesh] = set()
                    mesh_location_map[mesh].add(location)

        return mesh_location_map

    def get_participant_solver_map(self) -> dict[n.ParticipantNode, str]:
        """
        Create a dict mapping participant nodes to their solver.
        :return: A dict mapping participant nodes to their solver.
        """
        participant_solver_map: dict[n.ParticipantNode, str] = {}
        for participant_dict in self.topology["participants"]:
            # Get the participant node corresponding to the participant mentioned in the topology
            participant: n.ParticipantNode = next(p for p in self.participants if p.name == participant_dict["name"])
            # Assign the solver to the participant node
            participant_solver_map[participant] = participant_dict["solver"]
        return participant_solver_map

    def get_nodes(self) -> dict:
        """
        Return all nodes created from the topology.
        The returned dictionary has entries for the five major preCICE configuration elements, namely:
        Participants, Data, Meshes, CouplingSchemes and M2Ns.
        :return: A dictionary mapping node-names to lists of node-objects.
        """
        return {"participants": self.participants, "data": self.data, "meshes": self.meshes,
                "coupling-schemes": self.coupling_schemes, "m2n": self.m2ns}

    def _create_nodes(self) -> None:
        """
        Create ConfigGraph nodes based on the topology.
        """
        # Topology will only have tags "participants" and "exchanges"

        # Initialize participants from participants tag
        participant_map: dict[str, n.ParticipantNode] = self._initialize_participants()
        logger.debug(f"Created {len(set(participant_map.values()))} participant nodes.")

        # Create a dict mapping participants and their location names to location nodes
        participant_location_map: dict[tuple[n.ParticipantNode, str], helper.LocationNode] = self._initialize_locations(
            participant_map)

        # Initialize data from exchanges tag (defined implicitly)
        # This uses exchanges from the topology dict as keys, so the topology may not be modified afterward
        data_map: dict[frozenset, n.DataNode] = self._initialize_data()
        logger.debug(f"Created {len(set(data_map.values()))} data nodes.")

        # Initialize meshes from the exchanges tag (defined implicitly)
        mesh_map: dict[tuple[
            n.ParticipantNode, n.ParticipantNode, helper.DataKind, helper.LocationType], n.MeshNode] = self._initialize_meshes(
            participant_map, participant_location_map)
        logger.debug(f"Created {len(set(mesh_map.values()))} mesh nodes.")

        # Initialize mappings from the exchanges tag (defined implicitly)
        mapping_map: dict[tuple[n.MeshNode, n.MeshNode], n.MappingNode] = self._initialize_mappings(participant_map,
                                                                                                    mesh_map, data_map)
        logger.debug(f"Created {len(set(mapping_map.values()))} mapping nodes.")

        # Initialize exchanges from the exchanges tag
        potential_couplings: list[dict] = self._initialize_exchanges(participant_map, mesh_map, data_map, mapping_map)
        logger.debug(f"Created {len(potential_couplings)} exchange nodes.")

        # All potentially strong coupling-schemes
        strong_couplings: list[dict] = [coupling for coupling in potential_couplings if coupling["type"] == "strong"]
        logger.debug(f"Found {len(strong_couplings)} strong exchanges.")
        # All potentially weak coupling-schemes
        weak_couplings: list[dict] = [coupling for coupling in potential_couplings if coupling["type"] == "weak"]
        logger.debug(f"Found {len(weak_couplings)} weak exchanges.")

        # Maps participants to coupling schemes.
        coupling_map: dict[frozenset[n.ParticipantNode], n.CouplingSchemeNode | n.MultiCouplingSchemeNode] = {}
        # Handle strong couplings
        if len(strong_couplings) > 0:
            # This might manipulate weak_couplings, so this method needs to be called before _create_weak ...
            coupling_map = self._create_strong_coupling_schemes(strong_couplings, weak_couplings)

        # Handle weak couplings
        if len(weak_couplings) > 0:
            # The return value is not used anymore, but it looks nicer to have it here
            coupling_map = self._create_weak_coupling_schemes(weak_couplings, coupling_map)

        # Create M2Ns
        self._create_M2N()
        logger.debug(f"Created {len(self.m2ns)} M2N nodes.")

    def _create_M2N(self) -> None:
        """
        Create M2N nodes based on the coupling-schemes. Each pair of participants only needs one M2N.
        Inside a multi-coupling-scheme, every participant needs an M2N to the control participant;
        as well as to any participant they are exchanging data with.
        """
        # Map pairs of participants to M2N nodes to avoid duplicates
        m2n_map: dict[frozenset[n.ParticipantNode], n.M2NNode] = {}
        for coupling_scheme in self.coupling_schemes:
            # Treat multi-coupling-schemes separately: More than one M2N is needed here
            if isinstance(coupling_scheme, n.MultiCouplingSchemeNode):
                control_participant: n.ParticipantNode = coupling_scheme.control_participant
                # Create an M2N from the control participant to every other participant
                for participant in coupling_scheme.participants:
                    if participant != control_participant:
                        if frozenset((control_participant, participant)) not in m2n_map:
                            m2n: n.M2NNode = n.M2NNode(type=helper.DEFAULT_M2N_TYPE, acceptor=control_participant,
                                                       connector=participant)
                            m2n_map[frozenset((control_participant, participant))] = m2n
                            self.m2ns.append(m2n)
                            logger.debug(f"Created M2N from control-participant {control_participant.name} "
                                         f"to {participant.name}.")

                # Create an M2N for every exchange (once per pair of participants)
                for exchange in coupling_scheme.exchanges:
                    if frozenset((exchange.from_participant, exchange.to_participant)) not in m2n_map:
                        m2n: n.M2NNode = n.M2NNode(type=helper.DEFAULT_M2N_TYPE, acceptor=exchange.from_participant,
                                                   connector=exchange.to_participant)
                        m2n_map[frozenset((exchange.from_participant, exchange.to_participant))] = m2n
                        self.m2ns.append(m2n)
                        logger.debug(f"Created M2N from {exchange.from_participant.name} to "
                                     f"{exchange.to_participant.name}.")

            # Only one M2N is needed for a regular coupling-scheme (since there is only one pair of participants involved)
            elif isinstance(coupling_scheme, n.CouplingSchemeNode):
                first_participant: n.ParticipantNode = coupling_scheme.first_participant
                second_participant: n.ParticipantNode = coupling_scheme.second_participant
                if frozenset((first_participant, second_participant)) not in m2n_map:
                    m2n: n.M2NNode = n.M2NNode(
                        type=helper.DEFAULT_M2N_TYPE, acceptor=first_participant, connector=second_participant)
                    m2n_map[frozenset((first_participant, second_participant))] = m2n
                    self.m2ns.append(m2n)
                    logger.debug(f"Created M2N from {first_participant.name} to "
                                 f"{second_participant.name}.")

    def _create_strong_coupling_schemes(self, strong_couplings: list[dict], weak_couplings: list[dict]) \
            -> (dict[frozenset[n.ParticipantNode], n.CouplingSchemeNode | n.MultiCouplingSchemeNode]):
        """
        Create coupling-schemes for strong interactions.
        First, bidirectional strong couplings are determined. If there is more than one bidirectional strong coupling,
        a multi-coupling-scheme is created. Otherwise, if there is exactly one bidirectional strong coupling, an implicit
        coupling-scheme is created.
        Otherwise, no implicit coupling-scheme is created and all "strong" couplings are added to the "weak" couplings
        list to be handled by the ``_create_weak_coupling_schemes()`` method.
        Next, all potential couplings (both strong and weak) are inspected for couplings with participants involved in
        bidirectional strong couplings. Such participants are added to the implicit coupling-scheme.
        Finally, acceleration and convergence measures are added to every exchange of the implicit coupling-scheme.
        A dict mapping tuples of participants to coupling-schemes is returned.
        :param strong_couplings: A list of dicts with potential strong coupling schemes (exchanged of type "strong").
        :param weak_couplings: A list of dicts with potential weak coupling schemes (exchanged of type "weak").
        :return: A dict[frozenset[ParticipantNode], CouplingSchemeNode]
        """
        coupling_map: dict[frozenset[n.ParticipantNode], n.CouplingSchemeNode | n.MultiCouplingSchemeNode] = {}

        # All pairs of participants involved in bidirectional strong couplings
        bidirectional_strong_coupling_participant_pairs: set[frozenset[n.ParticipantNode]] = set()
        bidirectional_strong_couplings: list[dict] = []

        implicit_coupling_scheme: n.MultiCouplingSchemeNode | None = None

        # Iterate over all potential strong couplings
        for coupling in strong_couplings:
            # Check all other potential strong couplings to determine whether there are bidirectional strong couplings
            for other_coupling in strong_couplings:
                if coupling != other_coupling:
                    if coupling["from"] == other_coupling["to"] and coupling["to"] == other_coupling["from"]:
                        bidirectional_strong_coupling_participant_pairs.add(
                            frozenset((coupling["from"], coupling["to"])))
                        logger.debug(f"Found bidirectional strong coupling between {coupling['from'].name} "
                                     f"and {coupling['to'].name}.")
        logger.debug(f"There are {len(bidirectional_strong_coupling_participant_pairs)} participant pairs involved in "
                     f"bidirectional strong couplings.")

        # Check each potential strong coupling whether its participants are involved in bidirectional strong couplings
        # If so, add it to bidirectional_strong_couplings
        for coupling in strong_couplings:
            if frozenset((coupling["from"], coupling["to"])) in bidirectional_strong_coupling_participant_pairs:
                bidirectional_strong_couplings.append(coupling)

        unidirectional_strong_couplings: list[dict] = [coupling for coupling in strong_couplings if
                                                       coupling not in bidirectional_strong_couplings]
        logger.debug(f"There are {len(unidirectional_strong_couplings)} unidirectional strong exchanges and "
                     f"{len(bidirectional_strong_couplings)} bidirectional strong exchanges.")

        # We need a multi-coupling scheme if there is more than one bidirectional strong coupling
        if len(bidirectional_strong_coupling_participant_pairs) > 1:
            # Get all participants involved in bidirectional couplings (set to avoid duplicates)
            participants: set[n.ParticipantNode] = {participant for pair in
                                                    bidirectional_strong_coupling_participant_pairs
                                                    for participant in pair}
            participants: list[n.ParticipantNode] = list(participants)

            control_participant: n.ParticipantNode = self._determine_control_participant(participants,
                                                                                         bidirectional_strong_couplings)

            implicit_coupling_scheme: n.MultiCouplingSchemeNode = n.MultiCouplingSchemeNode(
                control_participant=control_participant,
                participants=participants)
            logger.debug(f"Created multi-coupling-scheme with control participant {control_participant.name} "
                         f"and participants: {', '.join(p.name for p in participants)}.")

            # Add all combinations of participants to the coupling-map
            for participant in participants:
                for other_participant in participants:
                    if participant != other_participant:
                        coupling_map[frozenset((participant, other_participant))] = implicit_coupling_scheme

        # Only one bidirectional strong coupling means implicit coupling-scheme
        elif len(bidirectional_strong_coupling_participant_pairs) == 1:
            # Extract the frozenset and sort the participants alphabetically by name to avoid random ordering
            participant_pair = list(bidirectional_strong_coupling_participant_pairs)[0]
            sorted_participants = sorted(participant_pair, key=lambda p: p.name)
            # Get both participants deterministically
            first: n.ParticipantNode = sorted_participants[0]
            second: n.ParticipantNode = sorted_participants[1]

            implicit_coupling_scheme: n.CouplingSchemeNode = n.CouplingSchemeNode(first_participant=first,
                                                                                  second_participant=second,
                                                                                  type=helper.DEFAULT_IMPLICIT_COUPLING_TYPE)
            coupling_map[frozenset((first, second))] = implicit_coupling_scheme
            participants: list[n.ParticipantNode] = [first, second]
            logger.debug(f"Created implicit coupling-scheme between {first.name} and {second.name}.")
        # No bidirectional strong coupling
        else:
            # No implicit coupling-scheme is required.
            # Add all strong ones to the weak couplings list and let the other method handle them
            logger.debug("No bidirectional strong couplings found. Adding all strong couplings to weak couplings list.")
            weak_couplings += strong_couplings

        # If an implicit coupling-scheme was created, exchanges, acceleration and convergence measures are added to it
        if implicit_coupling_scheme is not None:
            self.coupling_schemes.append(implicit_coupling_scheme)

            # Add bidirectional strong exchanges to the multi-coupling scheme
            for coupling in bidirectional_strong_couplings:
                coupling["exchange"].coupling_scheme = implicit_coupling_scheme
                implicit_coupling_scheme.exchanges.append(coupling["exchange"])

            # Check all other unidirectional strong couplings
            # Iterate over a copy to be able to remove elements from the list
            for coupling in unidirectional_strong_couplings.copy():
                # Both participants are already involved in the multi-coupling scheme
                # This means we add their exchange to the multi-coupling scheme
                if coupling["from"] in participants and coupling["to"] in participants:
                    coupling["exchange"].coupling_scheme = implicit_coupling_scheme
                    implicit_coupling_scheme.exchanges.append(coupling["exchange"])
                    # Remove this coupling from the list of unidirectional couplings, as it has already been added to the multi-coupling scheme
                    unidirectional_strong_couplings.remove(coupling)
                    logger.debug(f"Found unidirectional strong exchange between {coupling['from'].name} "
                                 f"and {coupling['to'].name} and added it to the implicit coupling-scheme.")

            # Check all weak couplings
            for coupling in weak_couplings.copy():
                # Both participants are already involved in the multi-coupling scheme
                # This means we add their exchange to the multi-coupling scheme
                if coupling["from"] in participants and coupling["to"] in participants:
                    coupling["exchange"].coupling_scheme = implicit_coupling_scheme
                    implicit_coupling_scheme.exchanges.append(coupling["exchange"])
                    # Remove this coupling from the list of couplings, as it has already been added to the multi-coupling scheme
                    weak_couplings.remove(coupling)
                    logger.debug(f"Found weak exchange between {coupling['from'].name} and {coupling['to'].name} "
                                 f"and added it to the implicit coupling-scheme.")

            # Add all remaining strong couplings to the weak couplings list
            weak_couplings += unidirectional_strong_couplings

            # Add acceleration and convergence measure for every exchange of the coupling-scheme
            acceleration: n.AccelerationNode = n.AccelerationNode(coupling_scheme=implicit_coupling_scheme,
                                                                  type=helper.DEFAULT_ACCELERATION_TYPE)
            implicit_coupling_scheme.acceleration = acceleration
            # Every exchanged data needs to be accelerated
            for exchange in implicit_coupling_scheme.exchanges:
                # If we added an acceleration-data node for this data-node and this mesh-node already, skip
                # This also includes skipping the convergence measure which has only these two degrees of freedom as well
                # (so the convergence measure is also defined only by the mesh and data, when the coupling-scheme is known)
                if any(d.data.name == exchange.data.name and d.mesh.name == exchange.mesh.name for d in
                       acceleration.data):
                    assert any(cv.data.name == exchange.data.name and cv.mesh.name == exchange.mesh.name for cv in
                               implicit_coupling_scheme.convergence_measures), ("Duplicate acceleration-data for mesh "
                                                                                f"{exchange.mesh.name} and data "
                                                                                f"{exchange.data.name}, but not duplicate "
                                                                                f"convergence-measure.")
                    continue
                acceleration_data: n.AccelerationDataNode = n.AccelerationDataNode(acceleration=acceleration,
                                                                                   data=exchange.data,
                                                                                   mesh=exchange.mesh)
                acceleration.data.append(acceleration_data)
                convergence_measure: n.ConvergenceMeasureNode = n.ConvergenceMeasureNode(
                    coupling_scheme=implicit_coupling_scheme,
                    type=helper.DEFAULT_CONVERGENCE_MEASURE_TYPE,
                    data=exchange.data,
                    mesh=exchange.mesh)
                implicit_coupling_scheme.convergence_measures.append(convergence_measure)
                logger.debug(f"Added acceleration and convergence-measure for data {exchange.data.name} "
                             f"on mesh {exchange.mesh.name}.")

        return coupling_map

    def _create_weak_coupling_schemes(self, weak_couplings: list[dict],
                                      coupling_map: dict[frozenset[n.ParticipantNode], n.CouplingSchemeNode]) -> (
            dict[frozenset[n.ParticipantNode], n.CouplingSchemeNode]):
        """
        Create coupling-schemes for weak interactions.
        :param weak_couplings: A list of dicts with potential weak coupling schemes.
        :param coupling_map: A map of already existing coupling-schemes.
        :return: A dict of all coupling-schemes, including the ones created in this method.
        """
        # All strong coupling-schemes have already been handled completely
        for weak_coupling in weak_couplings:
            from_participant: n.ParticipantNode = weak_coupling["from"]
            to_participant: n.ParticipantNode = weak_coupling["to"]
            # Check if these participants already have a coupling-scheme
            if frozenset((from_participant, to_participant)) not in coupling_map:
                # If so, create a new one
                coupling_scheme: n.CouplingSchemeNode = n.CouplingSchemeNode(type=helper.DEFAULT_EXPLICIT_COUPLING_TYPE,
                                                                             first_participant=from_participant,
                                                                             second_participant=to_participant)
                coupling_map[frozenset((from_participant, to_participant))] = coupling_scheme
                self.coupling_schemes.append(coupling_scheme)
                logger.debug(f"Created coupling-scheme between {from_participant.name} and {to_participant.name}.")

            else:
                # Otherwise, use the existing one
                coupling_scheme = coupling_map[frozenset((from_participant, to_participant))]
                logger.debug(
                    f"Found existing coupling-scheme between {from_participant.name} and {to_participant.name}.")
            # Add the exchange to the coupling-scheme
            coupling_scheme.exchanges.append(weak_coupling["exchange"])
            weak_coupling["exchange"].coupling_scheme = coupling_scheme
            logger.debug(f"Added exchange of data {weak_coupling['exchange'].data.name} on mesh "
                         f"{weak_coupling['exchange'].mesh.name} to the coupling-scheme.")

        return coupling_map

    def _initialize_exchanges(self, participant_map: dict[str, n.ParticipantNode],
                              mesh_map: dict[tuple[
                                  n.ParticipantNode, n.ParticipantNode, helper.DataKind, helper.LocationType], n.MeshNode],
                              data_map: dict[frozenset, n.DataNode],
                              mapping_map: dict[tuple[n.MeshNode, n.MeshNode], n.MappingNode]) -> list[dict]:
        """
        Initialize exchanges based on the exchanges-tag of the topology.
        Each exchange corresponds to one exchange node.
        This also creates "potential-couplings", as not every exchange needs a separate coupling-scheme.
        A potential coupling stores information about the exchange, from- and to-participant, and exchange-type.
        :param participant_map: A dict mapping participant names to participant nodes.
        :param mesh_map: A dict mapping participant pairs and "extensive/intensive" to mesh nodes.
        :param data_map: A dict mapping data names to data nodes.
        :return: A dict of potential couplings.
        """
        potential_couplings: list[dict] = []
        # An exchange is a dict "from, to, data, type, optional[data-type, from-/to-location-type], from-/to-location-name"
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            data: n.DataNode = data_map[frozenset(exchange.items())]
            from_location_type: helper.LocationType = exchange["from-location-type"]
            to_location_type: helper.LocationType = exchange["to-location-type"]
            data_label: helper.DataKind = helper.get_data_label(data.name.lower())
            from_mesh: n.MeshNode = mesh_map[(from_participant, to_participant, data_label, from_location_type)]
            to_mesh: n.MeshNode = mesh_map[(to_participant, from_participant, data_label, to_location_type)]

            # This will prevent exchanges between meshes of different dimensions from being created.
            # If this ever becomes allowed, this block can be removed.
            if from_mesh.dimensions != to_mesh.dimensions:
                max_dim: int = max(from_mesh.dimensions, to_mesh.dimensions)
                min_dim_mesh: n.MeshNode = from_mesh if from_mesh.dimensions != max_dim else to_mesh
                min_dim_mesh.dimensions = max_dim
                logger.warning(f"Mesh {from_mesh.name} and {to_mesh.name} have different dimensions. "
                               f"Mapping to meshes of different dimensions is not allowed. "
                               f"Setting {min_dim_mesh.name}'s dimensions to {max_dim} dimensions.")

            # Check type of mapping to determine which mesh is exchanged
            if mapping_map[(from_mesh, to_mesh)].direction == e.Direction.WRITE:
                # In a write-mapping, the exchanged mesh is the "to"-mesh
                exchange_node: n.ExchangeNode = n.ExchangeNode(coupling_scheme=None, data=data, mesh=to_mesh,
                                                               from_participant=from_participant,
                                                               to_participant=to_participant)
                logger.debug(f"Created exchange from {from_participant.name} to {to_participant.name} "
                             f"for data {data.name} on mesh {to_mesh.name}.")
            else:
                # In a read-mapping, the exchanged mesh is the "from"-mesh
                exchange_node: n.ExchangeNode = n.ExchangeNode(coupling_scheme=None, data=data, mesh=from_mesh,
                                                               from_participant=from_participant,
                                                               to_participant=to_participant)
                logger.debug(f"Created exchange from {from_participant.name} to {to_participant.name} "
                             f"for data {data.name} on mesh {from_mesh.name}.")
            # Either strong or weak
            exchange_type: str = exchange["type"]
            potential_couplings.append(
                {"exchange": exchange_node, "from": from_participant, "to": to_participant, "type": exchange_type})

        return potential_couplings

    def _initialize_mappings(self, participant_map: dict[str, n.ParticipantNode],
                             mesh_map: dict[tuple[
                                 n.ParticipantNode, n.ParticipantNode, helper.DataKind, helper.LocationType], n.MeshNode],
                             data_map: dict[frozenset, n.DataNode]) -> dict[
        tuple[n.MeshNode, n.MeshNode], n.MappingNode]:
        """
        Initialize all mappings. A mapping is needed between two participants if they exchange data over their meshes.
        For each pair of sender-mesh, receiver-mesh, a separate mapping is needed.
        The data (extensive or intensive) that is exchanged determines the type of mapping (write-conservative or read-consistent-mapping).
        :param participant_map: A dict mapping participant names to participant nodes.
        :param mesh_map: A dict mapping pairs of participants and "extensive/intensive" to mesh nodes.
        :param data_map: A dict mapping data names to data nodes.
        :return: A dict mapping (from-mesh, to-mesh) to mapping nodes.
        """
        # Keep track of which data was mentioned in a log message
        seen_data_with_unknown_label: set[n.DataNode] = set()
        # Map meshes to mapping nodes
        mapping_map: dict[tuple[n.MeshNode, n.MeshNode], n.MappingNode] = {}
        # Check for each exchange whether it already has a mapping and if not, create one
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            data: n.DataNode = data_map[frozenset(exchange.items())]
            from_location_type: helper.LocationType = exchange["from-location-type"]
            to_location_type: helper.LocationType = exchange["to-location-type"]

            # Get the label (extensive or intensive) to decide which mapping is needed
            data_label: helper.DataKind = helper.get_data_label(data.name.lower())
            if helper.is_unknown_data_kind(data.name) and data not in seen_data_with_unknown_label:
                logger.info(f"Data \"{data.name}\" is neither extensive nor intensive. Choosing default "
                            f"{helper.DEFAULT_DATA_KIND} with corresponding {helper.DEFAULT_MAPPING_KIND}-mapping.")
                seen_data_with_unknown_label.add(data)

            from_mesh: n.MeshNode = mesh_map[(from_participant, to_participant, data_label, from_location_type)]
            to_mesh: n.MeshNode = mesh_map[(to_participant, from_participant, data_label, to_location_type)]

            if data not in from_mesh.use_data:
                logger.debug(f"Adding use-data {data.name} to mesh {from_mesh.name}.")
                from_mesh.use_data.append(data)
            if data not in to_mesh.use_data:
                logger.debug(f"Adding use-data {data.name} to mesh {to_mesh.name}.")
                to_mesh.use_data.append(data)

            # Extensive data needs a conservative mapping,
            # so create a write-conservative mapping to allow for parallel participants
            if data_label == helper.DataKind.EXTENSIVE:
                logger.debug(f"Data {data.name} is extensive. Creating write-conservative mapping.")
                # If no mapping between from-mesh and to-mesh exists, create one
                if (from_mesh, to_mesh) not in mapping_map:
                    logger.debug(
                        f"No mapping between {from_mesh.name} and {to_mesh.name} exists. Creating new mapping.")
                    self._create_write_mapping(from_participant, to_participant, from_mesh, to_mesh, mapping_map)

            # Intensive data needs a consistent mapping,
            # so create a read-consistent mapping to allow for parallel participants
            elif data_label == helper.DataKind.INTENSIVE:
                logger.debug(f"Data {data.name} is intensive. Creating read-consistent mapping.")
                if (from_mesh, to_mesh) not in mapping_map:
                    logger.debug(
                        f"No mapping between {from_mesh.name} and {to_mesh.name} exists. Creating new mapping.")
                    self._create_read_mapping(from_participant, to_participant, from_mesh, to_mesh, mapping_map)
            else:
                logger.debug(f"Data {data.name} is {helper.DEFAULT_DATA_KIND}. Creating read-consistent mapping.")
                if (from_mesh, to_mesh) not in mapping_map:
                    logger.debug(
                        f"No mapping between {from_mesh.name} and {to_mesh.name} exists. Creating new mapping.")
                    self._create_read_mapping(from_participant, to_participant, from_mesh, to_mesh, mapping_map)

            # If a mapping already exists, then the participants already receive the corresponding meshes.
            # Regardless of whether a mapping already exists, write- and read-data tags need to be added.
            write_data: n.WriteDataNode = n.WriteDataNode(participant=from_participant, data=data, mesh=from_mesh)
            if not self._contains_write_data(write_data, from_participant.write_data):
                logger.debug(f"Adding write-data {data.name} to participant {from_participant.name}.")
                from_participant.write_data.append(write_data)

            read_data: n.ReadDataNode = n.ReadDataNode(participant=to_participant, data=data, mesh=to_mesh)
            if not self._contains_read_data(read_data, to_participant.read_data):
                logger.debug(f"Adding read-data {data.name} to participant {to_participant.name}.")
                to_participant.read_data.append(read_data)

        return mapping_map

    def _create_write_mapping(self, from_participant: n.ParticipantNode, to_participant: n.ParticipantNode,
                              from_mesh: n.MeshNode, to_mesh: n.MeshNode,
                              mapping_map: dict[tuple[n.MeshNode, n.MeshNode], n.MappingNode]) -> None:
        """
        Create a write-mapping between the given meshes.
        A write-mapping is located at the from-participant, who writes to their own mesh,
        receiving the to-mesh from the to-participant.
        :param from_participant: The participant who writes to the from-mesh and specifies the mapping.
        :param to_participant: The participant who sends their mesh to the from-participant.
        :param from_mesh: The mesh the from-participant writes to.
        :param to_mesh: The mesh the from-participant receives from the to-participant and is mapped to.
        :param mapping_map: A dict mapping (a-mesh, b-mesh) to mapping nodes.
        """
        # A write-mapping is on the from-participant, writing to his own mesh, receiving the to-mesh from the to-participant
        mapping: n.MappingNode = n.MappingNode(parent_participant=from_participant,
                                               direction=e.Direction.WRITE,
                                               from_mesh=from_mesh,
                                               to_mesh=to_mesh,
                                               just_in_time=False,
                                               constraint=e.MappingConstraint.CONSERVATIVE,
                                               method=helper.DEFAULT_MAPPING_METHOD)
        mapping_map[(from_mesh, to_mesh)] = mapping
        from_participant.mappings.append(mapping)
        # In a write-mapping, the writer has to receive the to-mesh to be able to map to it
        if not any(rm.mesh == to_mesh for rm in from_participant.receive_meshes):
            # Only add the receive-mesh if it is not already present.
            receive_mesh: n.ReceiveMeshNode = n.ReceiveMeshNode(participant=from_participant,
                                                                mesh=to_mesh,
                                                                from_participant=to_participant,
                                                                api_access=False)
            from_participant.receive_meshes.append(receive_mesh)
            logger.debug(f"Added receive-mesh {receive_mesh.mesh.name} to participant {from_participant.name}.")
        logger.debug(f"Created write-mapping between {from_mesh.name} and {to_mesh.name} "
                     f"for participant {from_participant.name}.")

    def _create_read_mapping(self, from_participant: n.ParticipantNode, to_participant: n.ParticipantNode,
                             from_mesh: n.MeshNode, to_mesh: n.MeshNode,
                             mapping_map: dict[tuple[n.MeshNode, n.MeshNode], n.MappingNode]) -> None:
        """
        Creates a read-mapping between the given meshes.
        A read-mapping is located at the to-participant, who reads from their own mesh,
        receiving the from-mesh from the from-participant.
        :param from_participant: The participant who sends their mesh to the to-participant.
        :param to_participant: The participant who specifies the mapping and reads from their own mesh.
        :param from_mesh: The mesh that is mapped from the from-participant to the to-participant.
        :param to_mesh: The mesh the to-participant reads from.
        :param mapping_map: A dict mapping (a-mesh, b-mesh) to mapping nodes.
        """
        # A read-mapping is on the to-participant, reading from his own mesh, receiving the from-mesh from the from-participant
        mapping: n.MappingNode = n.MappingNode(parent_participant=to_participant,
                                               direction=e.Direction.READ,
                                               from_mesh=from_mesh,
                                               to_mesh=to_mesh,
                                               just_in_time=False,
                                               constraint=e.MappingConstraint.CONSISTENT,
                                               method=helper.DEFAULT_MAPPING_METHOD)
        mapping_map[(from_mesh, to_mesh)] = mapping
        to_participant.mappings.append(mapping)
        # In a read-mapping, the reader has to receive the from-mesh to be able to map from it
        if not any(rm.mesh == from_mesh for rm in to_participant.receive_meshes):
            receive_mesh: n.ReceiveMeshNode = n.ReceiveMeshNode(participant=to_participant,
                                                                mesh=from_mesh,
                                                                from_participant=from_participant,
                                                                api_access=False)
            to_participant.receive_meshes.append(receive_mesh)
            logger.debug(f"Added receive-mesh {receive_mesh.mesh.name} to participant {to_participant.name}.")
        logger.debug(f"Created read-mapping between {from_mesh.name} and {to_mesh.name} "
                     f"for participant {to_participant.name}.")

    def _initialize_participants(self) -> dict[str, n.ParticipantNode]:
        """
        Initialize participant nodes and their dimensionality from the topology dict.
        Return a dictionary mapping participant names to participant nodes.
        :return: A dict[str, ParticipantNode]
        """
        participant_map: dict[str, n.ParticipantNode] = {}
        for participant in self.topology["participants"]:
            # The value is a dict that contains "name, solver, optional[dimensionality]"
            parzival: n.ParticipantNode = n.ParticipantNode(name=participant["name"])
            participant_map[participant["name"]] = parzival
            self.participants.append(parzival)
            dim: int = participant.get("dimensionality", helper.DEFAULT_PARTICIPANT_DIMENSIONALITY)
            if dim < 2 or dim > 3:
                logger.warning(f"Dimensionality of participant {parzival.name} is defined as {dim}. "
                               f"Setting it to {helper.DEFAULT_PARTICIPANT_DIMENSIONALITY}.")
                dim = helper.DEFAULT_PARTICIPANT_DIMENSIONALITY
            self.participant_dimensionality[parzival] = dim
            logger.debug(f"Initialized participant {parzival.name} with dimensionality {dim}.")
        return participant_map

    def _initialize_meshes(self, participant_map: dict[str, n.ParticipantNode],
                           participant_location_map: dict[tuple[n.ParticipantNode, str], helper.LocationNode]) -> \
            dict[tuple[n.ParticipantNode, n.ParticipantNode, helper.DataKind, helper.LocationType], n.MeshNode]:
        """
        Initialize all mesh nodes that are necessary to enable the exchanges in the topology.
        Partners that communicate with a participant over the exact same set of locations on that participant
        share a single mesh. Separate meshes are created depending on the data-kind (extensive or intensive)
        and location type (surface or volume) when required.

        :param participant_map: A dict mapping participant names to participant nodes.
        :param participant_location_map: A dict mapping participants and names of their locations to location nodes.
        :return: A dict mapping (from-participant, to-participant, data-kind, location-type) to mesh nodes.
        """
        # Step 1: Collect total location sets, mesh types, and directional data kinds per participant pair
        participant_pair_locations: dict[tuple[n.ParticipantNode, n.ParticipantNode], set[str]] = {}
        participant_mesh_type_map: dict[
            tuple[n.ParticipantNode, n.ParticipantNode], set[tuple[helper.DataKind, helper.LocationType]]] = {}
        participant_direction_kind_map: dict[tuple[n.ParticipantNode, n.ParticipantNode], set[helper.DataKind]] = {}

        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            data: str = exchange["data"]
            data_kind: helper.DataKind = helper.get_data_label(data)
            from_location_type: helper.LocationType = exchange["from-location-type"]
            to_location_type: helper.LocationType = exchange["to-location-type"]

            # Accumulate all locations used on each side of this participant pair
            participant_pair_locations.setdefault((from_participant, to_participant), set()).update(
                exchange["from-location-names"])
            participant_pair_locations.setdefault((to_participant, from_participant), set()).update(
                exchange["to-location-names"])

            # Symmetric: Store which types of meshes are needed for each communication partner
            participant_mesh_type_map.setdefault((from_participant, to_participant), set()).add(
                (data_kind, from_location_type))
            participant_mesh_type_map.setdefault((to_participant, from_participant), set()).add(
                (data_kind, to_location_type))

            # Non-symmetric: Store the data-kind exchanged in the direction of the exchange
            participant_direction_kind_map.setdefault((from_participant, to_participant), set()).add(data_kind)
            participant_direction_kind_map.setdefault((to_participant, from_participant), set())

        # Step 2: Group each participant's communication partners by the set of locations they use
        participant_location_groups: dict[n.ParticipantNode, dict[frozenset[str], set[n.ParticipantNode]]] = {
            p: {} for p in self.participants
        }
        for (from_participant, to_participant), locs in participant_pair_locations.items():
            loc_key = frozenset(locs)
            participant_location_groups[from_participant].setdefault(loc_key, set()).add(to_participant)

        # Step 3: Create meshes for each participant's location groups
        participant_mesh_map: dict[
            tuple[n.ParticipantNode, n.ParticipantNode, helper.DataKind, helper.LocationType], n.MeshNode] = {}

        for from_participant, loc_groups in participant_location_groups.items():
            num_groups: int = len(loc_groups)
            num_multi_partner_groups = sum(1 for partners in loc_groups.values() if len(partners) > 1)

            for partner_group in loc_groups.values():
                # Collect all (data_kind, location_type) requirements across all partners in this group
                group_mesh_types: set[tuple[helper.DataKind, helper.LocationType]] = set()
                for to_participant in partner_group:
                    group_mesh_types.update(participant_mesh_type_map[(from_participant, to_participant)])

                # A kind split is required if ANY partner in this group exchanges > 1 data kind in the same direction
                requires_kind_split: bool = any(
                    len(participant_direction_kind_map[(from_participant, to_participant)]) > 1
                    or len(participant_direction_kind_map[(to_participant, from_participant)]) > 1
                    for to_participant in partner_group
                )
                requires_loc_type_split: bool = len({loc for _, loc in group_mesh_types}) > 1

                created_meshes: dict[str, n.MeshNode] = {}

                for data_kind, location_type in group_mesh_types:
                    mesh_name: str = from_participant.name[:1].upper() + from_participant.name[1:]

                    # Only include partner name(s) if the participant has multiple distinct location groups
                    if num_groups > 1:
                        if len(partner_group) == 1:
                            only_partner: n.ParticipantNode = next(iter(partner_group))
                            mesh_name += "-" + only_partner.name[:1].upper() + only_partner.name[1:]
                        elif num_multi_partner_groups > 1:
                            sorted_partners: list[n.ParticipantNode] = sorted(partner_group, key=lambda p: p.name)
                            mesh_name += "-" + "-".join(p.name[:1].upper() + p.name[1:] for p in sorted_partners)

                    if requires_kind_split:
                        mesh_name += "-" + data_kind.value.capitalize()
                    if requires_loc_type_split:
                        mesh_name += "-" + location_type.value.capitalize()

                    if mesh_name not in created_meshes:
                        mesh: n.MeshNode = n.MeshNode(name=mesh_name + "-Mesh",
                                                      dimensions=self.participant_dimensionality[from_participant],
                                                      use_data=[])
                        self.meshes.append(mesh)
                        from_participant.provide_meshes.append(mesh)
                        created_meshes[mesh_name] = mesh

                    # Assign the shared mesh to every partner in this group that uses this (data_kind, location_type)
                    for to_participant in partner_group:
                        if (data_kind, location_type) in participant_mesh_type_map[(from_participant, to_participant)]:
                            participant_mesh_map[
                                (from_participant, to_participant, data_kind, location_type)] = created_meshes[
                                mesh_name]

        # Step 4: Loop over the exchanges again and assign mesh nodes to the correct location nodes
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            from_location_names: tuple[str] = exchange["from-location-names"]
            to_location_names: tuple[str] = exchange["to-location-names"]

            data: str = exchange["data"]
            data_kind: helper.DataKind = helper.get_data_label(data)
            from_location_type: helper.LocationType = exchange["from-location-type"]
            to_location_type: helper.LocationType = exchange["to-location-type"]

            from_mesh: n.MeshNode = participant_mesh_map[
                (from_participant, to_participant, data_kind, from_location_type)]
            to_mesh: n.MeshNode = participant_mesh_map[
                (to_participant, from_participant, data_kind, to_location_type)]

            for from_location_name in from_location_names:
                from_location: helper.LocationNode = participant_location_map[(from_participant, from_location_name)]
                if to_participant not in from_location.meshes:
                    from_location.meshes[to_participant] = {}
                from_location.meshes[to_participant][data_kind] = from_mesh

            for to_location_name in to_location_names:
                to_location: helper.LocationNode = participant_location_map[(to_participant, to_location_name)]
                if from_participant not in to_location.meshes:
                    to_location.meshes[from_participant] = {}
                to_location.meshes[from_participant][data_kind] = to_mesh

        return participant_mesh_map

    def _initialize_locations(self, participant_map: dict[str, n.ParticipantNode]) -> dict[
        tuple[n.ParticipantNode, str], helper.LocationNode]:
        """
        Initialize location nodes from the topology dict. 
        Return a dictionary mapping the owning participant and the location name to the location node.
        :param participant_map: A dict mapping participant names to participant nodes.
        :return: A dictionary mapping (participant, location-name) to LocationNode.
        """
        participant_location_map: dict[tuple[n.ParticipantNode, str], helper.LocationNode] = {}
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            from_location_names: list[str] = exchange["from-location-names"]
            for from_location_name in from_location_names:
                # We can safely access the location-type here, as it was assigned in the preprocessing step
                from_location_type: helper.LocationType = exchange["from-location-type"]
                # Create new location nodes if necessary. The meshes and label are not yet known.
                if (from_participant, from_location_name) not in participant_location_map:
                    location: helper.LocationNode = helper.LocationNode(name=from_location_name,
                                                                        participant=from_participant,
                                                                        type=from_location_type,
                                                                        meshes={})
                    participant_location_map[(from_participant, from_location_name)] = location
                    self.locations.append(location)

            to_location_names: list[str] = exchange["to-location-names"]
            for to_location_name in to_location_names:
                to_location_type: helper.LocationType = exchange["to-location-type"]
                if (to_participant, to_location_name) not in participant_location_map:
                    location: helper.LocationNode = helper.LocationNode(name=to_location_name,
                                                                        participant=to_participant,
                                                                        type=to_location_type,
                                                                        meshes={})
                    participant_location_map[(to_participant, to_location_name)] = location
                    self.locations.append(location)

        return participant_location_map

    def _determine_control_participant(self, participants: list[n.ParticipantNode],
                                       bidirectional_strong_couplings: list[dict]) -> n.ParticipantNode:
        """
        Determine the control participant for a multi-coupling scheme
        based on the frequency of each participant in bidirectional strong couplings.
        :param participants: The participants in the multi-coupling scheme.
        :param bidirectional_strong_couplings: The bidirectional strong couplings of the multi-coupling scheme.
        :return: The control participant as a ParticipantNode.
        """
        # Count how often participants appears in bidirectional couplings to determine the control participant
        frequency_map: dict[n.ParticipantNode, int] = {participant: 0 for participant in participants}
        for coupling in bidirectional_strong_couplings:
            frequency_map[coupling["from"]] += 1
            frequency_map[coupling["to"]] += 1
        # On a tie, it will choose the first participant in the list
        control_participant: n.ParticipantNode = max(frequency_map, key=frequency_map.get)
        logger.debug(f"Control participant determined to be {control_participant.name} "
                     f"with frequency {frequency_map[control_participant]}.")
        return control_participant

    def _initialize_data(self) -> dict[frozenset, n.DataNode]:
        """
        Initialize data nodes from the topology dict.
        Due to the heavy preprocessing, we can safely initialize data nodes based only on the name given in the topology.
        :return: A dict mapping exchanges to the corresponding data node.
        """
        # Keep track of created data nodes
        created_data: dict[str, n.DataNode] = {}
        # Map exchanges to data nodes. Use a frozenset since it is hashable and can be used as a key in a dict
        exchange_data_map: dict[frozenset, n.DataNode] = {}

        for exchange in self.topology["exchanges"]:
            data_name: str = helper.capitalize_name(exchange["data"])
            data_type: e.DataType = e.DataType(exchange["data-type"])

            if data_name not in created_data:
                data_node = n.DataNode(name=data_name, data_type=data_type)
                self.data.append(data_node)
                created_data[data_name] = data_node
                from_participant: str = exchange["from"]
                to_participant: str = exchange["to"]
                logger.debug(f"Created new data node {data_node.name} for data {data_name} "
                             f"between participants {from_participant} and {to_participant}")

            exchange_data_map[frozenset(exchange.items())] = created_data[data_name]

        return exchange_data_map

    def _contains_write_data(self, write_data: n.WriteDataNode, suspect_list: list[n.WriteDataNode]) -> bool:
        """
        Check if the given list of write-data nodes already contains the given write-data node.
        :param write_data: The write-data node to check for.
        :param suspect_list: The list of write-data nodes to check in.
        :return: True, if an equivalent write-data node already exists in the list. False otherwise.
        """
        for suspect in suspect_list:
            if suspect.data == write_data.data and suspect.mesh == write_data.mesh and suspect.participant == write_data.participant:
                logger.debug(f"Found write-data node with participant {suspect.participant.name}, "
                             f"mesh {suspect.mesh.name} and data {suspect.data.name}.")
                return True
        return False

    def _contains_read_data(self, read_data: n.ReadDataNode, suspect_list: list[n.ReadDataNode]) -> bool:
        """
        Check if the given list of read-data nodes already contains the given write-data node.
        :param read_data: The read-data node to check for.
        :param suspect_list: The list of read-data nodes to check in.
        :return: True, if an equivalent read-data node already exists in the list. False otherwise.
        """
        for suspect in suspect_list:
            if suspect.data == read_data.data and suspect.mesh == read_data.mesh and suspect.participant == read_data.participant:
                logger.debug(f"Found read-data node with participant {suspect.participant.name}, "
                             f"mesh {suspect.mesh.name} and data {suspect.data.name}.")
                return True
        return False
