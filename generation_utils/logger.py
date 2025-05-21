from enum import Enum
from pathlib import Path
from termcolor import colored
from datetime import datetime

class Level(Enum):
    INFO = ("INFO", "blue", "ℹ️")
    WARNING = ("WARNING", "yellow", "⚠️")
    SUCCESS = ("SUCCESS", "green", "✅")
    ERROR = ("ERROR", "red", "❌")

class Logger:
    def __init__(self, verbose: bool) -> None:
        """ Custom logger"""
        self.root_generated = Path(__file__).parent
        self.verbose = verbose
        self._errors = []
        self._warnings = []
        self._messages = []
    
    def clear_messages(self) -> None:
        """Clears all logged messages."""
        self._messages.clear()

    def print_formatted(self, msg: str, level: Level) -> None:
        """
        Internal method to print a message with a specified level, color, and symbol.
        :param msg: The log message.
        :param level: The log level (e.g., INFO, WARNING, SUCCESS, ERROR).
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        (level_name, color, symbol) = level.value
        formatted_msg = f"{timestamp} {symbol} [{level_name}] {msg}"
        if level != Level.INFO or self.verbose:
            print(colored(formatted_msg, color))

    def success(self, msg: str) -> None:
        """Logs a success message."""
        self.print_formatted(msg, Level.SUCCESS)

    def info(self, msg: str) -> None:
        """Logs an informational message."""
        self.print_formatted(msg, Level.INFO)

    def warning(self, msg: str) -> None:
        """Logs a warning message."""
        if not msg in self._warnings:
            self._warnings.append(msg)
        self.print_formatted(msg, Level.WARNING)

    def error(self, msg: str) -> None:
        """Logs an error message."""
        if not msg in self._errors:
            self._errors.append(msg)
        self.print_formatted(msg, Level.ERROR)
        
    def has_errors(self) -> bool:
        """Check if any errors have been logged."""
        return len(self._errors) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings have been logged."""
        return len(self._warnings) > 0

    def get_warnings(self) -> list:
        """Retrieve logged warnings."""
        return self._warnings

    def clear_log_state(self) -> None:
        """Clear all logged errors and warnings."""
        self._errors.clear()
        self._warnings.clear()
