"""
JSON-based logging setup for ionique session activity.

This module provides a decorator-based logging mechanism that records
function/method calls — including their class name, method name, timestamp,
and sanitized argument list — to a timestamped JSON file.  NumPy arrays and
plain lists are replaced with a ``"<numpy array>"`` placeholder so that the
log file remains small and fully JSON-serializable.

A module-level ``json_logger`` instance is created on import so that all
ionique submodules can share a single log file per Python session.
"""
import json
import functools
import logging
import numpy as np
import datetime


class JSONLogger:
    """
    Decorator-based logger that records function call metadata to a JSON file.

    Each call to a decorated function appends a JSON entry containing the
    invocation timestamp, class name, method name, and a sanitized
    representation of the arguments.  NumPy arrays and lists are replaced with
    a ``"<numpy array>"`` placeholder to keep entries compact and serializable.

    A new timestamped log file is created each time a ``JSONLogger`` instance
    is initialised, and the file is cleared (reset to an empty JSON array) on
    creation so that each session starts with a clean log.

    Attributes
    ----------
    filename : str
        Path to the JSON log file, named ``<YYYYMMDD_HHMMSS>_log.json``.
    logger : logging.Logger
        Standard-library logger used to emit exception tracebacks to stderr
        when a decorated function raises.
    """

    def __init__(self):
        """
        Initialise the JSON logger and create an empty log file.

        A timestamped filename is generated from the current wall-clock time,
        the log file is cleared to an empty JSON array, and a standard-library
        ``logging.Logger`` is configured at ``INFO`` level for exception
        reporting.
        """
        timestamp_init = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{timestamp_init}_log.json"
        self._clear_log_file()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _clear_log_file(self):
        """
        Clear the log file each time the kernel restarts.

        When the ``JSONLogger`` is initialised it dumps an empty list to the
        file so that subsequent appends always find valid JSON.
        """
        with open(self.filename, "w") as file:
            json.dump([], file)

    def _log_to_json(self, entry):
        """
        Append a new log entry to the JSON file.

        Parameters
        ----------
        entry : dict
            Mapping with keys ``"timestamp"``, ``"class"``, ``"method"``, and
            ``"arguments"`` describing a single function invocation.
        """
        with open(self.filename, "r+") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = []
            data.append(entry)
            file.seek(0)
            json.dump(data, file, indent=4)

    def log(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            """

            Avoid logging current and voltage arrays
            replacing numpy arrays with a placeholder

            """

            args_repr = []
            for a in args:
                if isinstance(a, np.ndarray):  # skip current numpy arrays
                    args_repr.append("<numpy array>")
                elif isinstance(a, list):  #  voltage list
                    args_repr.append("<numpy array>")
                else:
                    try:
                        args_repr.append(repr(a))
                    except Exception:
                        args_repr.append("<error in repr>")
            # Some arguments are objects that are not serializable.
            # Convert them to a string, otherwise
            kwargs_repr = []
            for k, v in kwargs.items():
                if isinstance(v, np.ndarray):
                    kwargs_repr.append(f"{k}=<numpy array>")
                else:
                    try:
                        kwargs_repr.append(f"{k}={repr(v)}")
                    except Exception:
                        kwargs_repr.append(f"{k}=<error in repr. arg=object>")

            signature = ", ".join(args_repr + kwargs_repr)

            # log class and method name if it's a method within a class
            class_name = args[0].__class__.__name__ if args else ""
            method_name = func.__name__

            # log entries
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "class": class_name,
                "method": method_name,
                "arguments": signature
            }

            # dump log the entry to JSON
            self._log_to_json(entry)

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                self.logger.exception(f"Exception raised in {method_name}. Exception: {str(e)}")
                raise e

        return wrapper


json_logger = JSONLogger()
