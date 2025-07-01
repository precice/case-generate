import pytest
import subprocess
import tempfile
from pathlib import Path

from preciceconfigcheck.cli import runCheck


def list_examples():
    examples = Path(__file__).parent.parent / "examples"
    return examples.rglob("topology.yaml")


@pytest.mark.parametrize("example", list_examples())
def test_application_with_example(example: Path):
    """Test the application with each example topology files"""

    assert example.exists() and example.is_file(), "topology file doesn't exist"

    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = ["precice-case-generate", "-f", str(example), "-o", temp_dir]
        print(f"Running {cmd}")
        subprocess.run(cmd)

        output = [p.name for p in Path(temp_dir).iterdir()]
        print(f"Output {output}")
        assert output, "Nothing generated"

        config = Path(temp_dir) / "precice-config.xml"
        assert config.exists(), "No config generated"
        ret = runCheck(config, True)
        if ret != 0:
            print("Failed config:")
            print(config.read_text())
            assert False, "The config failed to validate"
