import json
import hashlib
import shutil
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class StateTracker:
    def __init__(self, output_root: Path):
        """
        Initialize the StateTracker.
        :param output_root: The root directory of the generated project.
        """
        self.output_root = output_root
        self.state_file = output_root / ".file-state.json"
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """
        Load the previous state hashes if the file exists.
        :return: A dict mapping file paths to their hashes.
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not read state file: {e}")
        return {}

    def _hash_file(self, filepath: Path) -> str:
        """
        Generate a SHA-256 hash of a file.
        :param filepath: The path to the file.
        :return: The SHA-256 hash of the file as a hex string.
        """
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()

    def backup_modified_files(self) -> None:
        """
        Check all previously generated files. If their current hash differs from the saved hash,
        back them up before the generator overwrites them.
        """
        backup_dir: Path = None
        for rel_path_str, saved_hash in self.state.items():
            filepath: Path = self.output_root / rel_path_str
            if filepath.exists() and filepath.is_file():
                current_hash: str = self._hash_file(filepath)

                if current_hash != saved_hash:
                    # The user modified this file manually
                    if backup_dir is None:
                        timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S')
                        backup_dir = self.output_root / "backups" / f"{timestamp}"
                        backup_dir.mkdir(parents=True, exist_ok=True)

                    # Keep the relative folder structure inside the backup folder
                    backup_path: Path = backup_dir / rel_path_str
                    backup_path.parent.mkdir(parents=True, exist_ok=True)

                    # Move the file out of harm's way
                    shutil.move(str(filepath), str(backup_path))
                    logger.warning(f"File '{rel_path_str}' was manually modified. "
                                   f"Backed up to '{backup_path.relative_to(self.output_root)}'.")

    def save_new_state(self) -> None:
        """
        Hash all generated configuration and utility files and save the state.
        """
        new_state = {}
        # Track configurations and scripts (ignore preCICE logs, backups, etc.)
        tracked_extensions = {".xml", ".json", ".sh", ".md"}

        for filepath in self.output_root.rglob("*"):
            if filepath.is_file():
                rel_path_str = str(filepath.relative_to(self.output_root))

                # Skip the state file itself and anything in a backup folder
                if rel_path_str == self.state_file.name or "backup_" in rel_path_str:
                    continue

                if filepath.suffix in tracked_extensions:
                    new_state[rel_path_str] = self._hash_file(filepath)

        # Write the new state invisibly
        with open(self.state_file, "w") as f:
            json.dump(new_state, f, indent=4)
        logger.debug("File generation state tracked and saved.")
