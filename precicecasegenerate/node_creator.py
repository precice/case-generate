import random
import logging

from precice_config_graph import nodes as n
from precice_config_graph import enums as e
import precicecasegenerate.helper as helper

logger = logging.getLogger(__name__)


class NodeCreator:

    def __init__(self, topology: dict):
        self.topology = topology
        self.participants: list[n.ParticipantNode] = []
        self.data: list[n.DataNode] = []
        self.meshes: list[n.MeshNode] = []
        self.coupling_schemes: list[n.CouplingSchemeNode | n.MultiCouplingSchemeNode] = []
        self.m2ns: list[n.M2NNode] = []
        # Patches are important for adapter configs
        self.patches: list[helper.PatchNode] = []

        # Containers for temporary values
        # Dimensionality is needed for meshes
        self.participant_dimensionality: dict[n.ParticipantNode, int] = {}
        # self.data_types: dict[n.DataNode, e.DataType] = {}
        self.exchange_types: dict[n.ExchangeNode, str] = {}

        self._create_nodes()

    def get_mesh_patch_map(self) -> dict[n.MeshNode, set[str]]:
        """
        Create a dict mapping mesh nodes to sets of patches that they use / contain.
        :return: A dict mapping mesh nodes to sets of patches.
        """
        mesh_patch_map: dict[n.MeshNode, set[str]] = {}
        for patch in self.patches:
            mesh: n.MeshNode = patch.mesh
            # Create a a new entry if necessary
            if mesh not in mesh_patch_map:
                mesh_patch_map[mesh] = set()
            mesh_patch_map[mesh].add(patch.name)

        return mesh_patch_map

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
        # TODO check if topology does not contain duplicate participants;
        # TODO check that no data name contains one of the uniquifiers

        # Topology will only have tags "participants" and "exchanges"

        # Initialize participants from participants tag
        participant_map: dict[str, n.ParticipantNode] = self._initialize_participants()
        logger.debug(f"Created {len(set(participant_map.values()))} participant nodes.")

        # Update patches
        # IMPORTANT: This updates the topology dict.
        #  Anything using a "frozenset" of topology items needs to be done after this method!
        participant_patch_label_map: dict[tuple[n.ParticipantNode, n.ParticipantNode], dict[str, set[str]]] = (
            self._patch_preprocessing(participant_map))

        # Initialize data from exchanges tag (defined implicitly)
        # This uses the topology dict as keys, so it needs to be done after the patch preprocessing.
        data_map: dict[frozenset, n.DataNode] = self._initialize_data(participant_map)
        logger.debug(f"Created {len(set(data_map.values()))} data nodes.")

        # Initialize meshes from the exchanges tag (defined implicitly)
        mesh_map: dict[
            tuple[n.ParticipantNode, n.ParticipantNode, str], n.MeshNode] = self._initialize_meshes_and_patches(
            participant_patch_label_map)
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
                # Create an M2N for every exchange (once per pair of participants)
                for exchange in coupling_scheme.exchanges:
                    if frozenset((exchange.from_participant, exchange.to_participant)) not in m2n_map:
                        m2n: n.M2NNode = n.M2NNode(type=helper.DEFAULT_M2N_TYPE, acceptor=exchange.from_participant,
                                                   connector=exchange.to_participant)
                        m2n_map[frozenset((exchange.from_participant, exchange.to_participant))] = m2n
                        self.m2ns.append(m2n)
                        logger.debug(f"Created M2N from {exchange.from_participant.name} to "
                                     f"{exchange.to_participant.name}.")

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

    def _create_strong_coupling_schemes(self, strong_couplings: list[dict], weak_couplings: list[dict]) -> (
            dict[frozenset[n.ParticipantNode], n.CouplingSchemeNode]):
        """
        Create coupling-schemes for strong interactions.
        First, bidirectional strong couplings are determined. If there is more than one bidirectional strong coupling,
        a multi-coupling-scheme is created. Otherwise, if there is exactly one bidirectional strong coupling, an implicit
        coupling-scheme is created.
        Otherwise, no implicit coupling-scheme is created and all "strong" couplings are added to the "weak" couplings
        list to be handled by the ``_create_weak_coupling_schemes()`` method.
        Next, all potential couplings (both strong and weak) are searched for couplings with participants involved in
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
            # Get both participants
            first: n.ParticipantNode = list(list(bidirectional_strong_coupling_participant_pairs)[0])[0]
            second: n.ParticipantNode = list(list(bidirectional_strong_coupling_participant_pairs)[0])[1]
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
                              mesh_map: dict[tuple[n.ParticipantNode, n.ParticipantNode, str], n.MeshNode],
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
        # An exchange is a dict "from, to, data, type, optional[data-type], from_patch, to_patch"
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            data: n.DataNode = data_map[frozenset(exchange.items())]

            if any(data.name.lower().__contains__(extensive_data) for extensive_data in helper.EXTENSIVE_DATA):
                data_label: str = "extensive"
            elif any(data.name.lower().__contains__(intensive_data) for intensive_data in helper.INTENSIVE_DATA):
                data_label: str = "intensive"
            else:
                data_label: str = helper.DEFAULT_DATA_KIND

            from_mesh: n.MeshNode = mesh_map[(from_participant, to_participant, data_label)]
            to_mesh: n.MeshNode = mesh_map[(to_participant, from_participant, data_label)]

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
                             mesh_map: dict[tuple[n.ParticipantNode, n.ParticipantNode, str], n.MeshNode],
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
        mapping_map: dict[tuple[n.MeshNode, n.MeshNode], n.MappingNode] = {}
        # Check for each exchange whether it already has a mapping and if not, create one
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            data: n.DataNode = data_map[frozenset(exchange.items())]

            if any(data.name.lower().__contains__(extensive_data) for extensive_data in helper.EXTENSIVE_DATA):
                data_label: str = "extensive"
            elif any(data.name.lower().__contains__(intensive_data) for intensive_data in helper.INTENSIVE_DATA):
                data_label: str = "intensive"
            else:
                logger.warning(f"Data \"{data.name}\" is neither extensive nor intensive. Choosing default "
                               f"{helper.DEFAULT_DATA_KIND} with corresponding {helper.DEFAULT_MAPPING_KIND}-mapping.")
                data_label: str = helper.DEFAULT_DATA_KIND

            from_mesh: n.MeshNode = mesh_map[(from_participant, to_participant, data_label)]
            to_mesh: n.MeshNode = mesh_map[(to_participant, from_participant, data_label)]

            if data not in from_mesh.use_data:
                logger.debug(f"Adding use-data {data.name} to mesh {from_mesh.name}.")
                from_mesh.use_data.append(data)
            if data not in to_mesh.use_data:
                logger.debug(f"Adding use-data {data.name} to mesh {to_mesh.name}.")
                to_mesh.use_data.append(data)

            # Extensive data needs a conservative mapping,
            # so create a write-conservative mapping to allow for parallel participants
            if data_label == "extensive":
                logger.debug(f"Data {data.name} is extensive. Creating write-conservative mapping.")
                # If no mapping between from-mesh and to-mesh exists, create one
                if (from_mesh, to_mesh) not in mapping_map:
                    logger.debug(
                        f"No mapping between {from_mesh.name} and {to_mesh.name} exists. Creating new mapping.")
                    self._create_write_mapping(from_participant, to_participant, from_mesh, to_mesh, mapping_map)

            # Intensive data needs a consistent mapping,
            # so create a read-consistent mapping to allow for parallel participants
            else:
                logger.debug(f"Data {data.name} is intensive. Creating read-consistent mapping.")
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
        receive_mesh: n.ReceiveMeshNode = n.ReceiveMeshNode(participant=to_participant,
                                                            mesh=to_mesh,
                                                            from_participant=from_participant,
                                                            api_access=False)
        from_participant.receive_meshes.append(receive_mesh)
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
        receive_mesh: n.ReceiveMeshNode = n.ReceiveMeshNode(participant=to_participant,
                                                            mesh=from_mesh,
                                                            from_participant=from_participant,
                                                            api_access=False)
        to_participant.receive_meshes.append(receive_mesh)
        logger.debug(f"Created read-mapping between {from_mesh.name} and {to_mesh.name} "
                     f"for participant {to_participant.name}.")

    def _initialize_meshes_and_patches(self, participant_patch_map: dict[tuple[n.ParticipantNode, n.ParticipantNode],
    dict[str, set[str]]]) -> dict[tuple[n.ParticipantNode, n.ParticipantNode, str], n.MeshNode]:
        """
        Initialize meshes based on the communication of participants and the involved patches.
        First, communication between participants is counted to be able to determine the number of meshes needed and
        thus allow for better naming.
        Next, for each communication pair, mesh(es) are created based on the involved patches.
        During the mesh creation, while iterating over the patches, corresponding patch nodes are created.
        :param participant_patch_map: A dict mapping (a-participant, b-participant) to a dict of extensive and intensive patches.
        :return: A dict mapping (a-participant, b-participant, extensive/intensive) to mesh nodes.
        """
        # Count the frequency of a participant appearing in communications to determine the number of meshes to create
        frequency_map: dict[n.ParticipantNode, int] = {p1: 0 for p1, p2 in participant_patch_map}
        for (from_participant, to_participant) in participant_patch_map:
            # Since the map is symmetric, we only need to increment "from"
            frequency_map[from_participant] += 1
        # Create a dict mapping participant communication and data label to meshes
        participant_label_mesh_map: dict[tuple[n.ParticipantNode, n.ParticipantNode, str], n.MeshNode] = {}
        for (from_participant, to_participant) in participant_patch_map:
            # Check how many patches the from-participant uses in communication with the to-participant
            # Since the map is symmetric, it suffices to check the patches of "from"
            extensives: int = len(participant_patch_map[(from_participant, to_participant)]["extensive"])
            intensives: int = len(participant_patch_map[(from_participant, to_participant)]["intensive"])
            participant_dim: int = self.participant_dimensionality[from_participant]
            # Check if the communication uses both intensive and extensive data
            if extensives > 0 and intensives > 0:
                # Check if the from-participant communicates with more than one participant
                if frequency_map[from_participant] > 1:
                    # In this case, we name meshes "FROM-TO-Extensive/Intensive-Mesh"
                    # Capitalize only the first letter. This allows all-caps names
                    mesh_name: str = (f"{from_participant.name[:1].upper() + from_participant.name[1:]}"
                                      f"-{to_participant.name[:1].upper() + to_participant.name[1:]}")
                    extensive_mesh: n.MeshNode = n.MeshNode(name=mesh_name + "-Extensive-Mesh", use_data=[],
                                                            dimensions=participant_dim)
                    intensive_mesh: n.MeshNode = n.MeshNode(name=mesh_name + "-Intensive-Mesh", use_data=[],
                                                            dimensions=participant_dim)

                else:
                    # The participant communicates only with one other participant.
                    # The mesh is named "FROM-Extensive/Intensive-Mesh"
                    mesh_name: str = f"{from_participant.name[:1].upper() + from_participant.name[1:]}"
                    extensive_mesh: n.MeshNode = n.MeshNode(name=mesh_name + "-Extensive-Mesh", use_data=[],
                                                            dimensions=participant_dim)
                    intensive_mesh: n.MeshNode = n.MeshNode(name=mesh_name + "-Intensive-Mesh", use_data=[],
                                                            dimensions=participant_dim)
                # Add meshes to the respective containers
                from_participant.provide_meshes.append(extensive_mesh)
                from_participant.provide_meshes.append(intensive_mesh)
                self.meshes.append(extensive_mesh)
                self.meshes.append(intensive_mesh)
                participant_label_mesh_map[(from_participant, to_participant, "extensive")] = extensive_mesh
                participant_label_mesh_map[(from_participant, to_participant, "intensive")] = intensive_mesh
                logger.debug(f"Created extensive and intensive mesh for communication between "
                             f"{from_participant.name} and {to_participant.name}.")
                # Create new patch nodes for from_participant
                # Since only the patches of "from" are contained in
                # participant_patch_map[(from_participant, to_participant)], we must not create any patches for "to"
                for extensive_patch in participant_patch_map[(from_participant, to_participant)]["extensive"]:
                    patch_node: helper.PatchNode = helper.PatchNode(name=extensive_patch, participant=from_participant,
                                                                    mesh=extensive_mesh,
                                                                    label=helper.PatchState.EXTENSIVE)
                    self.patches.append(patch_node)
                for intensive_patch in participant_patch_map[(from_participant, to_participant)]["intensive"]:
                    patch_node: helper.PatchNode = helper.PatchNode(name=intensive_patch, participant=from_participant,
                                                                    mesh=intensive_mesh,
                                                                    label=helper.PatchState.INTENSIVE)
                    self.patches.append(patch_node)
            # The participant pair only communicates one kind of data
            else:
                # Check if the from-participant communicates with more than one participant
                if frequency_map[from_participant] > 1:
                    # In this case, we name meshes "FROM-TO-Mesh"
                    mesh_name: str = (f"{from_participant.name[:1].upper() + from_participant.name[1:]}"
                                      f"-{to_participant.name[:1].upper() + to_participant.name[1:]}")
                    mesh: n.MeshNode = n.MeshNode(name=mesh_name + "-Mesh", use_data=[],
                                                  dimensions=participant_dim)
                else:
                    # The participant communicates only with one other participant.
                    # The mesh is named "FROM-Mesh"
                    mesh_name: str = f"{from_participant.name[:1].upper() + from_participant.name[1:]}"
                    mesh: n.MeshNode = n.MeshNode(name=mesh_name + "-Mesh", use_data=[], dimensions=participant_dim)
                # Add the mesh to the respective container
                from_participant.provide_meshes.append(mesh)
                self.meshes.append(mesh)
                # Determine the kind of mesh this is (extensive or intensive)
                label: str = "extensive" if extensives > 0 else "intensive"
                participant_label_mesh_map[(from_participant, to_participant, label)] = mesh
                logger.debug(f"Created mesh for communication between {from_participant.name} "
                             f"and {to_participant.name}.")
                # Create new patch nodes for only this label
                for patch in participant_patch_map[(from_participant, to_participant)][label]:
                    patch_node: helper.PatchNode = helper.PatchNode(name=patch, participant=from_participant,
                                                                    mesh=mesh, label=helper.PatchState(label))
                    self.patches.append(patch_node)

        return participant_label_mesh_map

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

    def _patch_preprocessing(self, participant_map: dict[str, n.ParticipantNode]):
        """
        Preprocess patch labels in the topology.
        This is done by first assigning a label ("extensive" or "intensive") to each patch,
        then splitting them up if necessary; i.e., if they have both labels.
        Finally, a map (participant_1, participant_2) -> {extensive: {i_j}, intensive: {l_k}} is created,
        where an entry means that p1 uses extensive patches i_j and intensive patches l_k for communication with p2.
        :param participant_map: A dict mapping participant names to participant nodes.
        :return: A dict mapping participant pairs to patches used in communication between them.
        """
        participant_patch_label_map: dict[tuple[n.ParticipantNode, str], set[str]] = {}
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            from_patch: str = exchange["from-patch"]
            to_patch: str = exchange["to-patch"]
            data_name: str = exchange["data"]
            # Get data label
            if any(data_name.lower().__contains__(extensive_data) for extensive_data in helper.EXTENSIVE_DATA):
                data_label: str = "extensive"
            elif any(data_name.lower().__contains__(intensive_data) for intensive_data in helper.INTENSIVE_DATA):
                data_label: str = "intensive"
            else:
                data_label: str = "intensive"
            # Create new entries if necessary
            if (from_participant, from_patch) not in participant_patch_label_map:
                participant_patch_label_map[(from_participant, from_patch)] = set()
            if (to_participant, to_patch) not in participant_patch_label_map:
                participant_patch_label_map[(to_participant, to_patch)] = set()
            # Add the label to the patch
            participant_patch_label_map[(from_participant, from_patch)].add(data_label)
            participant_patch_label_map[(to_participant, to_patch)].add(data_label)

        # Map split-up patches to new patches
        participant_patch_new_patch_map: dict[tuple[n.ParticipantNode, str], dict[str, str]] = {}
        # Now, check if a patch has more than one label (i.e., both intensive and extensive)
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            from_patch: str = exchange["from-patch"]
            to_patch: str = exchange["to-patch"]
            data_name: str = exchange["data"]
            if any(data_name.lower().__contains__(extensive_data) for extensive_data in helper.EXTENSIVE_DATA):
                data_label: str = "extensive"
            elif any(data_name.lower().__contains__(intensive_data) for intensive_data in helper.INTENSIVE_DATA):
                data_label: str = "intensive"
            else:
                data_label: str = "intensive"

            # Check if this patch has been split up before
            if (from_participant, from_patch) in participant_patch_new_patch_map:
                # If so, then we just need to assign the new label to the patch
                exchange["from-patch"] = participant_patch_new_patch_map[(from_participant, from_patch)][data_label]
            # Else, if this patch has not been split, check if it needs to be split up
            elif len(participant_patch_label_map[(from_participant, from_patch)]) > 1:
                extensive_patch: str = f"{from_patch}-extensive"
                intensive_patch: str = f"{from_patch}-intensive"
                participant_patch_new_patch_map[(from_participant, from_patch)] = {"extensive": extensive_patch,
                                                                                   "intensive": intensive_patch}
                logger.warning(f"Split patch \"{from_patch}\" of participant {from_participant.name} into "
                               f"extensive patch \"{extensive_patch}\" and intensive patch \"{intensive_patch}\".")
                # Assign new patch name to the topology
                exchange["from-patch"] = extensive_patch if data_label == "extensive" else intensive_patch
            # If the patch has never been split and is not supposed to be split, nothing needs to be done

            # Check if this patch has been split up before
            if (to_participant, to_patch) in participant_patch_new_patch_map:
                # If so, then we just need to assign the new label to the patch
                exchange["to-patch"] = participant_patch_new_patch_map[(to_participant, to_patch)][data_label]
            # Else, if this patch has not been split, check if it needs to be split up
            elif len(participant_patch_label_map[(to_participant, to_patch)]) > 1:
                extensive_patch: str = f"{to_patch}-extensive"
                intensive_patch: str = f"{to_patch}-intensive"
                participant_patch_new_patch_map[(to_participant, to_patch)] = {"extensive": extensive_patch,
                                                                               "intensive": intensive_patch}
                logger.warning(f"Split patch \"{to_patch}\" of participant {to_participant.name} into "
                               f"extensive patch \"{extensive_patch}\" and intensive patch \"{intensive_patch}\".")
                # Assign new patch name to the topology
                exchange["to-patch"] = extensive_patch if data_label == "extensive" else intensive_patch
            # If the patch has never been split and is not supposed to be split, nothing needs to be done

        # Now create a map for which participant pair uses which patch
        # This means that for (p_1,p_2) -> {i_1,...,i_n}, p_1 uses i_j in communication with p_2; p_2 might use other patches
        participant_patch_map: dict[tuple[n.ParticipantNode, n.ParticipantNode], dict[str, set[str]]] = {}
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            from_patch: str = exchange["from-patch"]
            to_patch: str = exchange["to-patch"]
            data_name: str = exchange["data"]
            if any(data_name.lower().__contains__(extensive_data) for extensive_data in helper.EXTENSIVE_DATA):
                data_label: str = "extensive"
            elif any(data_name.lower().__contains__(intensive_data) for intensive_data in helper.INTENSIVE_DATA):
                data_label: str = "intensive"
            else:
                data_label: str = "intensive"
            # Initialize entries if necessary
            if (from_participant, to_participant) not in participant_patch_map:
                participant_patch_map[(from_participant, to_participant)] = {"extensive": set(), "intensive": set()}
                # If this direction does not yet exist, the other direction is also not initialized yet
                participant_patch_map[(to_participant, from_participant)] = {"extensive": set(), "intensive": set()}
            # From-participant uses from-patch in communication with to-participant
            participant_patch_map[(from_participant, to_participant)][data_label].add(from_patch)
            # To-participant uses to-patch in communication with from-participant
            participant_patch_map[(to_participant, from_participant)][data_label].add(to_patch)

        return participant_patch_map

    def _participant_patch_map(self, participant_map: dict[str, n.ParticipantNode]) -> dict[
        n.ParticipantNode, set[str]]:
        """
        Create a dictionary mapping each participant to a list of patches it uses.
        This is done by iterating over each exchange and adding the involved patches to the involved participants.
        This assumes self.participants and self.topology are already initialized.
        :param participant_map: A dict mapping participant names to participant nodes.
        :return: A dictionary dict[ParticipantNode, set[str]]
        """
        patch_map: dict[n.ParticipantNode, set[str]] = {p: set() for p in self.participants}
        for exchange in self.topology["exchanges"]:
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            patch_map[from_participant].add(exchange["from-patch"])

            to_participant: n.ParticipantNode = participant_map[exchange["to"]]
            patch_map[to_participant].add(exchange["to-patch"])
            logger.debug(f"Added entries for participant {from_participant.name} and patch {exchange['from-patch']}; "
                         f"as well as for participant {to_participant.name} and patch {exchange['to-patch']}.")
        return patch_map

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

    def _initialize_data(self, participant_map: dict[str, n.ParticipantNode]) -> dict[frozenset, n.DataNode]:
        """
        Initialize data nodes based on the participants and exchanges in the topology.
        If a participant tries to exchange both a scalar and a vector variant of data of the same name,
        the vector variant is preferred.
        :param participant_map: A dict mapping participant names to participant nodes.
        :return: A dict mapping exchanges to data nodes.
        """
        # Map exchanges to data nodes. Use a frozenset since it is hashable and can be used as a key in a dict
        exchange_data_map: dict[frozenset, n.DataNode] = {}
        # Map data names to their respective data nodes
        data_name_map: dict[str, n.DataNode] = {}
        # Map pairs of participants to data they exchange
        participant_data_map: dict[tuple[n.ParticipantNode, n.ParticipantNode], list[n.DataNode]] = {
            (p1, p2): [] for p1 in participant_map.values() for p2 in participant_map.values()
        }
        # Map pairs of participants and data names to data nodes
        participant_data_name_map: dict[tuple[n.ParticipantNode, n.ParticipantNode, str], n.DataNode] = {}

        for exchange in self.topology["exchanges"]:
            data_name: str = exchange["data"]
            data_type: e.DataType = exchange.get("data-type")
            data_type = e.DataType(data_type) if data_type else helper.DEFAULT_DATA_TYPE
            from_participant: n.ParticipantNode = participant_map[exchange["from"]]
            to_participant: n.ParticipantNode = participant_map[exchange["to"]]

            # Check if this data is known
            if data_name in data_name_map:
                data_node: n.DataNode = data_name_map[data_name]
                # Check if data is already exchanged between these participants in the other direction
                if ((to_participant, from_participant) in participant_data_map
                        and data_node in participant_data_map[(to_participant, from_participant)]):
                    # If so, the data name needs to be uniquified (and a new data node needs to be created),
                    # to avoid both participants writing and reading this data
                    uniquifier: str = helper.get_uniquifier()
                    new_data_name: str = f"{uniquifier.capitalize()}-{helper.capitalize_name(data_name)}"
                    logger.warning(f"Data name \"{data_name}\" is exchanged by participants {from_participant.name} "
                                   f"and {to_participant.name} in both directions. Using \"{new_data_name}\" "
                                   f"for one direction.")
                    data_node = n.DataNode(name=new_data_name, data_type=data_type)
                    data_name_map[new_data_name] = data_node
                    self.data.append(data_node)
                    logger.debug(f"Data {data_name} is already exchanged between participants {to_participant.name} "
                                 f"and {from_participant.name}. Created new data node {data_node.name} for the direction "
                                 f"{from_participant} to {to_participant} with uniquified data name.")
                # Otherwise, check if the already-exchanged-data has a different type than the current data
                elif data_type != data_node.data_type:
                    # Since the data types do not agree, we know that one uses vector data and the other scalar data
                    # The default is vector, so we choose the vector variant
                    logger.warning(f"Data {data_name} is used by multiple exchanges with different data types. "
                                   f"Using data-type=\"{e.DataType.VECTOR.value}\" for all exchanges.")
                    data_node.data_type = e.DataType.VECTOR

            # This data is unknown, so we create a new data node
            else:
                data_node: n.DataNode = n.DataNode(name=helper.capitalize_name(data_name), data_type=data_type)
                data_name_map[data_name] = data_node
                logger.debug(f"Created new data node {data_node.name} for data {data_name} "
                             f"between participants {from_participant.name} and {to_participant.name}")
                self.data.append(data_node)

            participant_data_map[(from_participant, to_participant)].append(data_node)
            participant_data_name_map[(from_participant, to_participant, data_name)] = data_node
            exchange_data_map[frozenset(exchange.items())] = data_node

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
