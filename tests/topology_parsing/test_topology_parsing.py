from ruamel.yaml import YAML

def test_scientific_notation_parsing():
    """
    Test that YAML scientific notation (e.g., 1e-2) is parsed as a float, not a string.
    """
    yaml = YAML(typ="safe")

    parsed_value = yaml.load("1e-2")

    assert isinstance(parsed_value, float), "Scientific notation was parsed as a string."
    assert parsed_value == 0.01