"""
This file tests the correct execution of the clean.sh script.
"""
import subprocess
from pathlib import Path

from precicecasegenerate.cli import generate_case


# This directory is the same for all tests in this file.


def test_clean_script():
    """
    Check that all topologies generate valid preCICE config files.
    """
    test_directory: Path = Path(__file__).parent
    case_directory: Path = test_directory
    generated_directory: Path = case_directory / "_generated"

    input_file: Path = case_directory / "topology.yaml"

    assert 0 == generate_case(input_file, generated_directory), "Case generation failed."

    # Create files that should be deleted (inside _generated)
    log_file = generated_directory / "precice-1234.log"
    log_file.touch()

    vtk_file = generated_directory / "dummy_solver" / "mesh.vtk"
    vtk_file.parent.mkdir(parents=True, exist_ok=True)
    vtk_file.touch()

    # precice-run directory should be deleted
    precice_run_dir = generated_directory / "precice-run"
    precice_run_dir.mkdir(parents=True, exist_ok=True)
    (precice_run_dir / "some_internal_file.txt").touch()

    # Empty folder should be deleted
    suspicious_folder = generated_directory / "suspicious_folder"
    suspicious_folder.mkdir(parents=True, exist_ok=True)

    # Create a file that should be kept (inside _generated)
    custom_script = generated_directory / "my_custom_script.py"
    custom_script.touch()

    # Create a file above the _generated directory that should thus not be deleted
    outside_artifact = test_directory / "precice-9999.log"
    outside_artifact.touch()

    # Execute the clean.sh script
    result = subprocess.run(
        [generated_directory / "clean.sh"],
        cwd=test_directory,  # Run it from inside the test directory
        capture_output=True,  # Capture the echo print statements
        text=True  # Return strings instead of bytes
    )

    # Ensure the script ran successfully (return code 0)
    assert result.returncode == 0, f"clean.sh failed! Error: {result.stderr}"

    # These files should have been deleted
    assert not log_file.exists(), "preCICE log file was not deleted."
    assert not vtk_file.exists(), "VTK mesh file was not deleted."
    assert not precice_run_dir.exists(), "precice-run directory was not deleted."
    assert not vtk_file.parent.exists(), "Empty dummy_solver directory was not cleaned up."
    assert not suspicious_folder.exists(), "Suspicious folder was not deleted."

    # These files should have been kept
    assert custom_script.exists(), "Custom user files were accidentally deleted."
    assert (generated_directory / "precice-config.xml").exists(), "precice-config.xml was accidentally deleted."
    assert (generated_directory / "clean.sh").exists(), "clean.sh deleted itself."  # 🥀
    assert (generated_directory / "generator-asolver").exists(), "generator-asolver was deleted."
    assert (generated_directory / "generator-asolver" / "adapter-config.json").exists(), "generator-asolver/adapter-config.json was deleted."
    assert (generated_directory / "generator-asolver" / "run.sh").exists(), "generator-asolver/run.sh was deleted."
    assert (generated_directory / "propagator-bsolver").exists(), "propagator-bsolver was deleted."
    assert (generated_directory / "propagator-bsolver" / "adapter-config.json").exists(), "propagator-bsolver/adapter-config.json was deleted."
    assert (generated_directory / "propagator-bsolver" / "run.sh").exists(), "propagator-bsolver/run.sh was deleted."
    assert (generated_directory / "README.md").exists(), "README.md was deleted."

    # These files should not have been deleted due to living above the _generated directory that contains the clean.sh script
    assert outside_artifact.exists(), "clean.sh escaped its ROOT_DIR and deleted outside files."
    assert (test_directory / "topology.yaml").exists(), "topology.yaml was deleted."

    # Remove the "outside" file
    outside_artifact.unlink()
