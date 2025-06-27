import pytest
import subprocess
import tempfile
from pathlib import Path


def list_examples():
    examples = Path(__file__).parent.parent / "examples"
    return examples.rglob("topology.yaml")


@pytest.mark.parametrize("example", list_examples())
def test_application_with_example(tmp_path, example: Path):
    """Test the application with each example topology files"""

    assert example.exists() and example.is_file(), "topology file doesn't exist"

    cmd = ["precice-case-generate", "-f", str(example), "-o", str(tmp_path)]
    print(f"Running {cmd}")
    subprocess.run(cmd, check=True)

    output = list(tmp_path.iterdir())
    print(f"Output {[p.name for p in output]}")
    assert output, "Nothing generated"

    config = tmp_path / "precice-config.xml"

    assert config.exists(), "No precice-config.xml generated"

    subprocess.run(["precice-cli", "config", "check", str(config)], check=True)
