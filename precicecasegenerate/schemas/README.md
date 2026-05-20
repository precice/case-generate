# The Topology File

A `topology.yaml` file is the only file needed to run this program. 

> [!NOTE] As a YAML file, the topology is case-, indent- and whitespace-sensitive.


The JSON schema of the topology can be found in the `topology-schema.json` file.

It consists of two main elements:

- `participants`: The solvers involved in the simulation.
- `exchanges`: How the solvers interact with one another.

## Participants

The `participants` element describes the main actors of the simulation through given `name`s and the `solver`s they use. 
It can hold an arbitrary number of elements, which must have pairwise unique names. 
The optional parameter `dimensionality` defines the dimensions of the meshes used by the participant.

There must be at least one participant defined, however, for a successful communication to be possible, 
at least two participants must exist.
A valid entry might look as follows:

```yaml
participants:
  - name: Crocodile     # An arbitrary string
    solver: SeeYouLater # An arbitrary string
    dimensionality: 3   # Either 2, 3 or not given
  - name: Alligator
    solver: InAWhile
  - ...
```

## Exchanges

The `exchanges` element describes how the main actors of the simulation communicate and relate to one-another.
This means that a single exchange needs to define a source participant `from`, a destination participant `to` and 
patches (interfaces) of these participants through `from-patch` and `to-patch`. 
The data that is exchanges is given as `data` and the type of the exchange (strong (implicit) or weak (explicit)) 
is chosen through `type`.
The optional parameter `data-type` can take either of the two values `scalar` or `vector`. 
If not given, a value might be inferred from the name of the `data`.

At least one exchange must exist for a valid topology. Exchanges must be unique.
A valid entry might look as follows:

```yaml
exchanges:
  - from: Crocodile     # A string that corresponds to a previously defined participant
    to: Alligator       # A string that corresponds to a previously defined participant
    from-patch: claw    # A patch (interface) of the `from`-participant
    to-patch: claw      # A patch (interface) of the `to`-participant
    type: strong        # The type of the data-exchange; either `strong` (implicit) or `weak` (explicit)
    data: fish          # The data that is being exchanged
    data-type: vector   # The type of the data that is being exchange; either `scalar`,`vector` or not given
  - ...
```

## Example

A complete example for a valid `topology.yaml` file is the following:

```yaml
participants:
  - name: Crocodile     # An arbitrary string
    solver: SeeYouLater # An arbitrary string
    dimensionality: 3   # Either 2, 3 or not given
  - name: Alligator
    solver: InAWhile
exchanges:
  - from: Crocodile     # A string that corresponds to a previously defined participant
    to: Alligator       # A string that corresponds to a previously defined participant
    from-patch: claw    # A patch (interface) of the `from`-participant
    to-patch: claw      # A patch (interface) of the `to`-participant
    type: strong        # The type of the data-exchange; either `strong` (implicit) or `weak` (explicit)
    data: fish          # The data that is being exchanged
    data-type: vector
```

## Legacy

In version 1 of preCICE Case Generate, the topology had the additional elements `coupling-scheme` and `acceleration`. 
To facilitate the usage of the tool, they were removed and the parameters are now either inferred from the remaining 
two tags or assigned a default value.