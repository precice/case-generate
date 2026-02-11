# preCICE Case Generate

preCICE case-generate is a python based utility designed to simplify the generation of preCICE application cases. 
Such cases consist of the central `precice-config.xml` file which defines all sorts of connections and relations between 
involved solvers, as well as `adapter-config.json` files for each solver. 

These files involve a lot of complex elements and modifiers, which are often times not needed. 
This tool introduces a simpler, easier to read and write `topology.yaml` file, 
which covers a wide range of features of the `precice-config.xml` file, yet with only a fraction of the complexity.
An overview over the `topology.yaml` file can be found in `precicecasegenerate/schemas/README.md`.

## Key Features

- Automated preCICE configuration generation
- YAML-based input parsing
- Flexible topology description support
- Comprehensive error logging and handling
- Simple command-line interface

## Getting Started

### Prerequisites

Required dependencies are:

- Python ≥ 3.10 
- pip
- git for cloning the repository :) 
- [preCICE Config Graph](https://github.com/precice/config-graph)  (will be installed during the setup)
- pyyaml
- jsonschema

Optional dependencies are:

- pytest
- [preCICE Config Check](https://github.com/precice/config-check)

### Manual Installation

1. Clone the repository

```bash
git clone https://github.com/precice/case-generate.git
cd case-generate
```

2. Create a virtual environment

```bash
# On Unix/macOS
python -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
.\venv\Scripts\activate
```

3. Install the project

```bash
# Upgrade pip and install build tools
python -m pip install --upgrade pip
pip install build

# Install the project in editable mode
pip install -e .
```

Optional dependencies for testing can be installed via 
```bash
pip install -e ".[dev]"
```

### Using Setup Scripts

#### Unix/macOS

```bash
./setup_scripts/install_dependencies.sh
```

#### Windows

```powershell
.\setup_scripts\install_dependencies.ps1
```

### Verifying Installation

- Test the CLI tool

```bash
precice-case-generate --help
```

## Usage

### Command-Line Interface

Generate a preCICE configuration file from a YAML topology called `topology.yaml`:

```bash
precice-case-generate path/to/topology.yaml
```

The only required argument is the `path/to/topology.yaml`.

The `precice-case-generate` tool supports the following optional parameters:

- `-o, --output-path`: Destination path for the generated folder.
  - **Default**: `./_generated/`
  - **Description**: Choose a specific output location for the `_generated/` directory.

- `-v, --verbose`: Enable verbose console logging.
  - **Default**: Disabled
  - **Description**: Provides detailed logging information during execution.


> [!NOTE]
> While it is not expected, the topology generation might fail or produce faulty configuration files. 
> This might happen in situations where the `topology.yaml` contains multiple edge cases, 
> such as many data exchanges with the same `data`-tag. 
> The preCICE [Config Check](https://github.com/precice/config-check) is designed to identify and alert to such errors.

### Examples

Valid `topology.yaml` <-> application case pairs can be found in the `examples/` directory. 
They include the preCICE tutorials 1-4 as well as some more complex simulations.  

### Configuration

1. Prepare a YAML topology file describing your multi-physics simulation setup.
2. Use the command-line interface to generate the preCICE configuration.
3. preCICE Case Generate will create the necessary configuration files in the `_generated/` directory.

## Creating Topologies with MetaConfigurator

You can create a topology for your preCICE simulation using the online MetaConfigurator.
We provide a preloaded schema to help you get started:

1. Open the MetaConfigurator with the preloaded
   schema: [MetaConfigurator link](https://metaconfigurator.github.io/meta-configurator/?schema=https://github.com/precice/case-generate/blob/main/precicecasegenerate/schemas/topology-schema.json&settings=https://github.com/precice/case-generate/blob/main/precicecasegenerate/templates/metaConfiguratorSettings.json)

2. Use the interactive interface to define your topology:
    - The preloaded schema provides a structured way to describe your simulation components

3. Once complete, export your topology as a YAML file
    - Save the generated YAML file
    - Use `precice-case-generte` to create your preCICE application case and configuration files
    - Validate the generated preCICE config with [config-checker](https://github.com/precice/config-check)

## Documentation

The template for our `topology.yaml` file can be found in the `schemas` folder.

Alongside it, you will find `README.md`, which explains the topology's parameters.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

## Troubleshooting

- Ensure all dependencies are correctly installed
- Verify the format of your input YAML file
- Check the generated logs (`./.logs`) for detailed process information

If all else fails, open a pull request describing the issue you are encountering. 