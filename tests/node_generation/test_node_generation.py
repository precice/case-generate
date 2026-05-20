from pathlib import Path
from precice_config_graph import nodes as n, enums as e
from precice_config_graph.nodes import MeshNode

from precicecasegenerate.input_handler.topology_reader import TopologyReader
from precicecasegenerate.node_creator import NodeCreator
import precicecasegenerate.helper as helper

test_directory: Path = Path(__file__).parent


def simple_setup(patches: bool = False) -> tuple[dict, dict, dict[MeshNode, set[str]]] | tuple[dict, dict]:
    """
    Create all nodes for the (simple) test topology file.
    :return: A dict representing the topology and a dict containing all nodes created from the topology.
    """
    topology_file: Path = test_directory / "simple_topology.yaml"

    topology_reader: TopologyReader = TopologyReader(topology_file)
    topology: dict = topology_reader.get_topology()
    node_creator: NodeCreator = NodeCreator(topology)
    nodes: dict = node_creator.get_nodes()
    if patches:
        return topology, nodes, node_creator.get_mesh_patch_map()
    return topology, nodes


def complex_setup() -> tuple[dict, dict]:
    """
    Create all nodes for the (more complex) test topology file.
    :return: A dict representing the topology and a dict containing all nodes created from the topology.
    """
    topology_file: Path = test_directory / "complex_topology.yaml"

    topology_reader: TopologyReader = TopologyReader(topology_file)
    topology: dict = topology_reader.get_topology()
    node_creator: NodeCreator = NodeCreator(topology)
    nodes: dict = node_creator.get_nodes()
    return topology, nodes


def test_participant_nodes():
    """
    Check that all attributes of the participant nodes are correct.
    """
    topology, nodes = simple_setup()
    number_of_participants: int = len(topology["participants"])
    participants: list[n.ParticipantNode] = nodes["participants"]
    assert len(participants) == number_of_participants, (f"Found {len(participants)} participants, "
                                                         f"expected {number_of_participants}.")

    first_name: str = None
    try:
        first_name = topology["participants"][0]["name"]
        first_participant: n.ParticipantNode = next(p for p in participants if p.name == first_name)
    except StopIteration:
        assert False, f"Participant {first_name} not found."
    second_name: str = None
    try:
        second_name = topology["participants"][1]["name"]
        second_participant: n.ParticipantNode = next(p for p in participants if p.name == second_name)
    except StopIteration:
        assert False, f"Participant {second_name} not found."

    assert len(nodes["data"]) == 1, f"Found {len(nodes['data'])} data nodes, expected 1."
    data: n.DataNode = nodes["data"][0]

    if first_participant.read_data and second_participant.read_data:
        assert False, "Both participants have read-data nodes."
    elif not first_participant.read_data and not second_participant.read_data:
        assert False, "Neither participant has read-data nodes."

    read_participant: n.ParticipantNode = first_participant if first_participant.read_data else second_participant
    try:
        next(rd for rd in read_participant.read_data if rd.data == data)
    except StopIteration:
        assert False, f"Data {data.name} not found in reader-participant {read_participant.name}."

    if first_participant.write_data and second_participant.write_data:
        assert False, "Both participants have write-data nodes."
    elif not first_participant.write_data and not second_participant.write_data:
        assert False, "Neither participant has write-data nodes."

    write_participant: n.ParticipantNode = first_participant if first_participant.write_data else second_participant
    try:
        next(wd for wd in write_participant.write_data if wd.data == data)
    except StopIteration:
        assert False, f"Data {data.name} not found in writer-participant {write_participant.name}."

    assert write_participant != read_participant, f"The same participant {write_participant.name} reads and writes data."

    from_name: str = topology["exchanges"][0]["from"]
    to_name: str = topology["exchanges"][0]["to"]
    from_participant: n.ParticipantNode = first_participant if from_name == first_name else second_participant
    to_participant: n.ParticipantNode = first_participant if to_name == first_name else second_participant
    assert from_participant != to_participant, f"Exchange is between the same participant {from_name}."

    assert len(first_participant.provide_meshes) == 1, f"Participant {first_name} provides more than one mesh."
    assert len(second_participant.provide_meshes) == 1, f"Participant {second_name} provides more than one mesh."

    # Bools for checking mappings
    extensive_case: bool = data.name in helper.EXTENSIVE_DATA
    intensive_case: bool = data.name in helper.INTENSIVE_DATA
    if not extensive_case and not intensive_case:
        if helper.DEFAULT_DATA_KIND == "extensive":
            extensive_case = True
        else:
            intensive_case = True

    if extensive_case:
        # For extensive data, a write-mapping is needed. A write-mapping is specified by the from-participant.
        assert write_participant == from_participant, f"From-participant {from_name} does not write data {data.name}."
        assert from_participant.mappings, f"Write mapping is not specified by the from-participant {from_name}."
        assert not to_participant.mappings, f"To-participant {to_name} specifies mapping."
        assert len(from_participant.mappings) == 1, f"From-participant {from_name} specifies more than one mapping."
        # Then the from-participant also receives a mesh from the to-participant
        assert len(from_participant.receive_meshes) == 1, (f"From-participant {from_name} receives "
                                                           f"{len(from_participant.receive_meshes)} meshes, expected 1.")
        assert not to_participant.receive_meshes, f"To-participant {to_name} receives a mesh."
        receive_mesh_node: n.ReceiveMeshNode = from_participant.receive_meshes[0]
        assert receive_mesh_node.mesh == to_participant.provide_meshes[0], (
            f"From-participant {from_name} receives mesh {receive_mesh_node.mesh.name}."
        )

        mapping: n.MappingNode = from_participant.mappings[0]
        # Write-mappings are always conservative
        assert mapping.constraint == e.MappingConstraint.CONSERVATIVE, (f"Write mapping is not conservative "
                                                                        f"but has type {mapping.constraint.value}")
        assert mapping.direction == e.Direction.WRITE, f"Write-mapping is not a write-mapping."

    elif intensive_case:
        # For intensive data, a read-mapping is needed. A read-mapping is specified by the to-participant.
        assert read_participant == to_participant, f"To-participant {to_name} does not read data {data.name}."
        assert to_participant.mappings, f"Read mapping is not specified by the to-participant {to_name}."
        assert not from_participant.mappings, f"From-participant {from_name} specifies mapping."
        assert len(to_participant.mappings) == 1, f"To-participant {to_name} specifies more than one mapping."
        # Then the to-participant also receives a mesh from the from-participant
        assert len(to_participant.receive_meshes) == 1, (f"To-participant {to_name} does not receives "
                                                         f"{len(to_participant.receive_meshes)} meshes, expected 1.")
        assert not from_participant.receive_meshes, f"From-participant {from_name} receives a mesh."
        receive_mesh_node: n.ReceiveMeshNode = to_participant.receive_meshes[0]
        assert receive_mesh_node.mesh == from_participant.provide_meshes[0], (
            f"To-participant {to_name} receives mesh {receive_mesh_node.mesh.name}."
        )

        mapping: n.MappingNode = to_participant.mappings[0]
        # Read-mappings are always consistent
        assert mapping.constraint == e.MappingConstraint.CONSISTENT, (f"Read-mapping is not consistent "
                                                                      f"but has type {mapping.constraint.value}")
        assert mapping.direction == e.Direction.READ, f"Read-mapping is not a read-mapping."

    assert mapping.method == helper.DEFAULT_MAPPING_METHOD, (f"Mapping method is {mapping.method.value}, "
                                                             f"expected {helper.DEFAULT_MAPPING_METHOD.value}.")
    # The from_mesh should be by the from-participant
    assert mapping.from_mesh == from_participant.provide_meshes[0], (
        f"Mapping uses wrong from-mesh {mapping.from_mesh.name} ,"
        f"expected {from_participant.provide_meshes[0].name}."
    )
    # The to_mesh should be by the to-participant
    assert mapping.to_mesh == to_participant.provide_meshes[0], (f"Mapping uses wrong to-mesh {mapping.to_mesh.name}, "
                                                                 f"expected {to_participant.provide_meshes[0].name}.")

    # These attributes are never set by this project and should therefore be empty / None
    assert not mapping.just_in_time, "Mapping is just-in-time."
    # A mapping-node has more attributes, but these are not used if the method is NEAREST_NEIGHBOR, as is expected here

    # These attributes are never set by this project and should therefore be empty / None
    for participant in nodes["participants"]:
        assert not participant.watchpoints, f"Participant {participant.name} specifies watchpoints."
        assert not participant.watch_integrals, f"Participant {participant.name} specifies watch-integrals."
        assert not participant.exports, f"Participant {participant.name} specifies exports."
        assert not participant.actions, f"Participant {participant.name} specifies actions."


def test_explicit_coupling_scheme_nodes():
    """
    Check that all attributes of the (explicit) coupling-scheme nodes are correct.
    """
    topology, nodes = simple_setup()
    coupling_scheme_nodes: list[n.CouplingSchemeNode] = nodes["coupling-schemes"]
    assert len(coupling_scheme_nodes) == 1, (
        f"Found {len(coupling_scheme_nodes)} coupling schemes, expected 1.")

    coupling_scheme: n.CouplingSchemeNode = coupling_scheme_nodes[0]

    # Since there is only one exchange, the type is always explicit
    assert coupling_scheme.type == helper.DEFAULT_EXPLICIT_COUPLING_TYPE

    first_participant: n.ParticipantNode = coupling_scheme.first_participant
    second_participant: n.ParticipantNode = coupling_scheme.second_participant
    assert first_participant != second_participant, f"Coupling-scheme is between the same participants {first_participant.name}."

    assert len(coupling_scheme.exchanges) == len(topology["exchanges"]), (
        f"Found {len(coupling_scheme.exchanges)} exchanges, expected {len(topology['exchanges'])}."
    )

    from_name: str = topology["exchanges"][0]["from"]
    to_name: str = topology["exchanges"][0]["to"]
    from_participant: n.ParticipantNode = first_participant if from_name == first_participant.name else second_participant
    to_participant: n.ParticipantNode = first_participant if to_name == first_participant.name else second_participant

    assert from_participant == coupling_scheme.exchanges[0].from_participant, (
        f"From-participant {from_name} of coupling-scheme does not match the exchange's from-participant "
        f"{coupling_scheme.exchanges[0].from_participant.name}."
    )

    assert to_participant == coupling_scheme.exchanges[0].to_participant, (
        f"To-participant {to_name} of coupling-scheme does not match the exchange's to-participant "
        f"{coupling_scheme.exchanges[0].to_participant.name}."
    )
    # These attributes should not be set for an explicit coupling-scheme
    assert not coupling_scheme.acceleration, f"Coupling-scheme specifies accelerations."
    assert not coupling_scheme.convergence_measures, f"Coupling-scheme specifies convergence measures."


def test_multi_coupling_scheme_nodes():
    """
    Check that attributes of the multi-coupling-scheme nodes are set correctly.
    """
    topology, nodes = complex_setup()
    multi_coupling_scheme_nodes: list[n.MultiCouplingSchemeNode] = nodes["coupling-schemes"]
    assert len(multi_coupling_scheme_nodes) == 1, (f"Found {len(multi_coupling_scheme_nodes)} multi-coupling schemes, "
                                                   f"expected 1.")

    multi_coupling_scheme: n.MultiCouplingSchemeNode = multi_coupling_scheme_nodes[0]
    assert isinstance(multi_coupling_scheme,
                      n.MultiCouplingSchemeNode), f"Coupling-scheme is not a multi-coupling scheme."

    multi_coupling_scheme_participants: list[n.ParticipantNode] = multi_coupling_scheme.participants

    assert len(multi_coupling_scheme_participants) == len(topology["participants"]), (
        f"The topology specifies {len(topology['participants'])} participants, the coupling-scheme has {len(multi_coupling_scheme_participants)} participants."
    )

    exchange_nodes: list[n.ExchangeNode] = multi_coupling_scheme.exchanges
    topology_exchanges: list[dict] = topology["exchanges"]

    assert len(exchange_nodes) == len(topology_exchanges), (
        f"The topology specifies {len(topology_exchanges)} exchanges, the coupling-scheme has {len(exchange_nodes)} exchanges."
    )
    # Check that the control participant is involved in the most exchanges
    # and check that each exchange node has a corresponding exchange in the topology
    exchange_histogramm: dict[n.ParticipantNode, int] = {p: 0 for p in multi_coupling_scheme_participants}
    for exchange in topology_exchanges:
        from_name: str = exchange["from"]
        to_name: str = exchange["to"]
        data_name: str = exchange["data"]
        try:
            exchange_node: n.ExchangeNode = next(e for e in exchange_nodes if e.from_participant.name == from_name and
                                                 e.to_participant.name == to_name and e.data.name == data_name)
            from_participant: n.ParticipantNode = exchange_node.from_participant
            to_participant: n.ParticipantNode = exchange_node.to_participant
        except StopIteration:
            assert False, f"Exchange {from_name}->{to_name} with data {data_name} not found in multi-coupling-scheme."
        exchange_histogramm[from_participant] += 1
        exchange_histogramm[to_participant] += 1

    most_popular_participant: n.ParticipantNode = max(exchange_histogramm, key=exchange_histogramm.get)
    assert multi_coupling_scheme.control_participant == most_popular_participant, (
        f"The most popular participant in the coupling-scheme is {multi_coupling_scheme.control_participant.name}, "
        f"expected {most_popular_participant.name}."
    )

    assert multi_coupling_scheme.acceleration, "Multi-coupling scheme does not specify an acceleration."

    acceleration: n.AccelerationNode = multi_coupling_scheme.acceleration
    assert acceleration.type == helper.DEFAULT_ACCELERATION_TYPE, (f"Acceleration type is {acceleration.type.value}, "
                                                                   f"expected {helper.DEFAULT_ACCELERATION_TYPE.value}.")

    assert len(acceleration.data) == len(topology_exchanges), (
        f"The topology specifies {len(topology_exchanges)} exchanges, "
        f"but len{acceleration.data} are accelerated."
    )

    # Check that each accelerated data corresponds to an exchange
    for accelerated_data in acceleration.data:
        try:
            next(e for e in topology_exchanges if e["data"] == accelerated_data.data.name)
        except StopIteration:
            assert False, f"Accelerated data {accelerated_data.data.name} not found in topology."
    # Since there are the same number of acceleration-data-nodes as exchanges in the topology,
    # this means that each exchange is accelerated exactly once

    assert multi_coupling_scheme.convergence_measures, "Multi-coupling scheme does not specify convergence measures."
    assert len(multi_coupling_scheme.convergence_measures) == len(topology_exchanges), (
        f"The topology specifies {len(topology_exchanges)} exchanges, "
        f"but {len(multi_coupling_scheme.convergence_measures)} convergence measures are specified."
    )

    # Check that each convergence measure corresponds to an exchange
    for convergence_measure in multi_coupling_scheme.convergence_measures:
        try:
            next(e for e in topology_exchanges if e["data"] == convergence_measure.data.name)
        except StopIteration:
            assert False, f"Convergence-measure for data {convergence_measure.data.name} not found in topology."
    # Again, this means that there is a bijection between exchanges and convergence measures

    # These attributes are not set during node creation
    assert not acceleration.preconditioner, "Acceleration specifies a preconditioner."
    assert not acceleration.filter, "Acceleration specifies a filter."


def test_m2n_nodes():
    """
    Test that the M2N nodes are created correctly.
    """
    topology, nodes = complex_setup()
    m2n_nodes: list[n.M2NNode] = nodes["m2n"]

    # Check that each exchange in the topology has an M2N node connecting the exchanges' participants
    for exchange in topology["exchanges"]:
        from_name: str = exchange["from"]
        to_name: str = exchange["to"]
        try:
            next(m2n for m2n in m2n_nodes if ((m2n.acceptor.name == from_name and m2n.connector.name == to_name)
                                              or (m2n.acceptor.name == to_name and m2n.connector.name == from_name)))
        except StopIteration:
            assert False, f"No M2N node found connecting {from_name} and {to_name}."

    # Check each M2N node connect participants that exchange something
    for m2n in m2n_nodes:
        acceptor_name: str = m2n.acceptor.name
        connector_name: str = m2n.connector.name
        assert acceptor_name != connector_name, f"M2N node between same participant {acceptor_name}."
        try:
            next(e for e in topology["exchanges"] if ((e["from"] == acceptor_name and e["to"] == connector_name)
                                                      or (e["from"] == connector_name and e["to"] == acceptor_name)))
        except StopIteration:
            assert False, f"No exchange found between {acceptor_name} and {connector_name}."
        assert m2n.directory, f"M2N node between {acceptor_name} and {connector_name} does not specify a directory."
        assert m2n.type == helper.DEFAULT_M2N_TYPE, (f"M2N type is {m2n.type.value}, "
                                                     f"expected {helper.DEFAULT_M2N_TYPE.value}.")


def test_data_nodes():
    """
    Test that data nodes are created correctly.
    """
    topology, nodes = simple_setup()
    data_nodes: list[n.DataNode] = nodes["data"]
    # Check that each exchange in the topology has a data node
    for exchange in topology["exchanges"]:
        data_name: str = exchange["data"]
        data_type: str = exchange.get("data-type", helper.DEFAULT_DATA_TYPE)
        try:
            # Note: This is only an approximate scheme, as data names can be uniquified
            # and might thus not match original names completely
            data_node = next(dn for dn in data_nodes if data_name.lower() in dn.name.lower())
        except StopIteration:
            assert False, f"No data node found for data {data_name}."
        assert data_node.data_type.value == data_type, (f"Data node {data_name} has type {data_node.data_type.value}, "
                                                        f"expected {data_type}.")

    for data_node in data_nodes:
        try:
            # Note: This is only an approximate scheme, as data names can be uniquified
            # and might thus not match original names completely
            exchange = next(e for e in topology["exchanges"] if e["data"].lower() in data_node.name.lower())
        except StopIteration:
            assert False, f"Data node {data_node.name} does not have an exchange."
        assert data_node.data_type.value == exchange.get("data-type", helper.DEFAULT_DATA_TYPE), (
            f"Data node {data_node.name} has type {data_node.data_type.value}, "
            f"expected {exchange.get('data-type', helper.DEFAULT_DATA_TYPE)}."
        )


def test_mesh_nodes():
    """
    Check that mesh nodes are created correctly.
    """
    topology, nodes, mesh_patch_map = simple_setup(patches=True)
    mesh_nodes: list[n.MeshNode] = nodes["meshes"]

    # Check that each mesh is provided by exactly one participant
    for mesh in mesh_nodes:
        try:
            provider: n.ParticipantNode = next(p for p in nodes["participants"] if mesh in p.provide_meshes)
            impostor: n.ParticipantNode = next(p for p in nodes["participants"][::-1] if mesh in p.provide_meshes)
        except StopIteration:
            assert False, f"Mesh {mesh.name} is not provided by any participant."
        assert provider == impostor, f"Mesh {mesh.name} is provided by both {provider.name} and {impostor.name}."

        assert mesh.use_data, f"Mesh {mesh.name} does not use any data."

        # Check the dimensions of the mesh
        dimensionality: int = next(p.get("dimensionality", helper.DEFAULT_PARTICIPANT_DIMENSIONALITY)
                                   for p in topology["participants"] if p["name"] == provider.name)
        # It can happen in a "legal" way that the dimensions do not match:
        # If A maps something to B and one has a higher dimensionality than the other,
        # the highest dimensionality of the two is used.
        increase_dim: bool = False
        if not mesh.dimensions == dimensionality:
            # We need to check if there exists a mapping involving this mesh that has a higher dimensionality
            # Since the mapping of this topology is a read-mapping, the "provider" participant defined the mapping
            for mapping in provider.mappings:
                if mapping.from_mesh == mesh:
                    assert mapping.to_mesh.dimensions >= dimensionality, (
                        f"Mesh {mesh.name} has dimensions {mesh.dimensions}, "
                        f"expected at least {mapping.to_mesh.dimensions}."
                    )
                    increase_dim = True
                    break
                elif mapping.to_mesh == mesh:
                    assert mapping.from_mesh.dimensions >= dimensionality, (
                        f"Mesh {mesh.name} has dimensions {mesh.dimensions}, "
                        f"expected at least {mapping.from_mesh.dimensions}."
                    )
                    increase_dim = True
                    break
            assert increase_dim, (f"Mesh {mesh.name} has dimensions {mesh.dimensions}, "
                           f"expected {dimensionality}.")

    # Check that each mesh is in the mesh-patch map
    for mesh in mesh_nodes:
        assert mesh in mesh_patch_map, f"Mesh {mesh.name} is not in the mesh-patch map."
        # Check that the patch in the mesh-patch-map is in the topology
        patch_names: set[str] = mesh_patch_map[mesh]
        for patch_name in patch_names:
            try:
                # Note: This is only an approximate scheme, since patch names are not unique
                next(e for e in topology["exchanges"] if e["from-patch"] == patch_name or e["to-patch"] == patch_name)
            except StopIteration:
                assert False, f"Patch {patch_name} is not in any exchange in the topology."

    # Check that each patch in the topology is in the mesh-patch map
    for exchange in topology["exchanges"]:
        from_patch_name: str = exchange["from-patch"]
        try:
            next(m for m in mesh_nodes if from_patch_name in mesh_patch_map[m])
        except StopIteration:
            assert False, f"Patch {from_patch_name} is not in any mesh in the mesh-patch map."

        to_patch_name: str = exchange["to-patch"]
        try:
            next(m for m in mesh_nodes if to_patch_name in mesh_patch_map[m])
        except StopIteration:
            assert False, f"Patch {to_patch_name} is not in any mesh in the mesh-patch map."
