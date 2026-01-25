import datetime
import logging
from logging import LogRecord, Logger
from pathlib import Path
from precicecasegenerate import cli_helper


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.INFO: "\033[32m",  # green
        logging.DEBUG: "\033[34m",  # blue
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[1;31m"  # bold red
    }
    RESET = "\033[0m"

    def format(self, record: LogRecord) -> str:
        """
        Format a log record, such that the levelname is colored according to the level.
        :param record: The log record to format.
        :return: The formatted log record.
        """
        # Store original levelname
        levelname = record.levelname
        color = self.COLORS.get(record.levelno, "")
        record.levelname = f"{color}{levelname}{self.RESET}"
        formatted = super().format(record)
        # Restore original levelname
        record.levelname = levelname
        return formatted


def setup_logging(verbose: bool = False) -> Logger:
    """
    Create a logger object and set up logging to a file and the console.
    By default, only warnings and errors are logged to the console, whereas everything is logged to the file.
    :param verbose: Enables debug logging to the console.
    :return: A logger object.
    """
    log_directory: Path = Path(cli_helper.LOG_DIR_NAME)
    log_directory.mkdir(parents=True, exist_ok=True)

    # Base level is debug (nothing is ignored)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Delete old log files if there are more than 10 to avoid clutter
    log_files = sorted(log_directory.glob("precice-case-generate-*.log"))
    if len(log_files) >= 10:
        for old_file in log_files[:-9]:
            try:
                # This deletes the file
                old_file.unlink()
            except OSError as e:
                logger.warning(f"Error deleting old log file {old_file}: {e}")

    timestamp: str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_path: Path = log_directory / f"precice-case-generate-{timestamp}.log"

    # Prevent duplicate handlers incase this method is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Write everything to a log file
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.DEBUG)
    # Only write warnings and errors to the console
    console_handler = logging.StreamHandler()
    if not verbose:
        console_handler.setLevel(logging.INFO)
    else:
        console_handler.setLevel(logging.DEBUG)

    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    # Use a file_formatter with color
    console_formatter = ColorFormatter(
        "[%(asctime)s] [%(levelname)s]: %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.debug(f"Logs can be found in {log_directory.resolve()}")

    return logger
