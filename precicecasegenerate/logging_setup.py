import os
import datetime
import glob
import logging
from logging import LogRecord, Logger


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
        :return:
        """
        # Store original levelname
        levelname = record.levelname
        color = self.COLORS.get(record.levelno, "")
        record.levelname = f"{color}{levelname}{self.RESET}"
        formatted = super().format(record)
        record.levelname = levelname  # Restore
        return formatted


def setup_logging(verbose: bool = False) -> Logger:
    timestamp: str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    path: str = ".logs/"
    os.makedirs(path, exist_ok=True)

    # Delete old log files if there are more than 10 to avoid clutter
    log_files = sorted(glob.glob(os.path.join(path, "precice-case-generate-*.log")))
    if len(log_files) >= 10:
        for old_file in log_files[:len(log_files) - 9]:
            os.remove(old_file)

    log_filename = f"{path}precice-case-generate-{timestamp}.log"

    # Base level is debug (nothing is ignored)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Write everything to a log file
    file_handler = logging.FileHandler(log_filename)
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

    logger.debug("Logs can be found in .logs/")

    return logger
