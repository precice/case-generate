"""
This file tests the functionality of the StateTracker and the file generation process.
"""
import shutil
from pathlib import Path

from precicecasegenerate.cli import generate_case


def test_state_tracker():
    """
    Check that running the generator again preserves custom files
    and correctly backs up modified generated files before overwriting.
    """
    test_directory: Path = Path(__file__).parent
    input_file: Path = test_directory / "topology.yaml"
    generated_directory: Path = test_directory / "_generated"

    # Remove any previously generated files
    if generated_directory.exists():
        shutil.rmtree(generated_directory, ignore_errors=True)

    # Generate initial files
    assert 0 == generate_case(input_file, generated_directory), "Initial case generation failed."

    # Find the solver directory dynamically
    solver_dirs: list[Path] = [d for d in generated_directory.iterdir()
                               if d.is_dir() and "-" in d.name and not d.name.startswith("backup")]
    assert len(solver_dirs) > 0, "No solver directory found."
    solver_dir = solver_dirs[0]

    # Add a custom file to the first solver directory
    custom_file: Path = solver_dir / "info.txt"
    custom_file.write_text("This is my custom mesh data.")

    # Modify a generated file to simulate a manual edit
    run_script: Path = solver_dir / "run.sh"
    modified_content: str = run_script.read_text() + "\n# USER MODIFIED CONTENT\n"
    run_script.write_text(modified_content)

    # Run the generator a second time
    assert 0 == generate_case(input_file, generated_directory), "Second case generation failed."

    # Check that the custom file survived
    assert custom_file.exists(), "Custom file was destroyed."
    assert custom_file.read_text() == "This is my custom mesh data.", "Custom file content was altered."

    # Check that the original file was overwritten with the template
    new_run_script_content: str = run_script.read_text()
    assert "# USER MODIFIED CONTENT" not in new_run_script_content, "The run.sh file was not overwritten with the template."

    backups_root: Path = generated_directory / "backups"
    assert backups_root.exists(), "The 'backups' directory was not created."

    # Check that exactly one backup folder was created by the StateTracker
    backup_dirs: list[Path] = list(backups_root.glob("*"))
    assert len(backup_dirs) == 1, f"Expected 1 backup directory, found {len(backup_dirs)}."
    backup_dir = backup_dirs[0]

    # D) Check that the modified file was moved to the backup folder properly
    # The relative structure is preserved, so it should be inside _generated/backups/<timestamp>/generator-asolver/run.sh
    backed_up_file: Path = backup_dir / solver_dir.name / "run.sh"

    assert backed_up_file.exists(), f"Modified file was not backed up to {backed_up_file}."
    assert "# USER MODIFIED CONTENT" in backed_up_file.read_text(), "Backed up file does not contain manual edits."
