import re
import sys
import logging.config


class NamedLogger(logging.LoggerAdapter):
    """
    A logging adapater that uses the passed name in square brackets as
    a prefix.

    The ``extra`` arguments are ``name``, a string. If ``name`` is not present
    or if it's ``None``, no prefix is used.
    """

    def process(self, msg, kwargs):
        try:
            prefix = f"[{self.extra['name']}]: "
        except KeyError:
            prefix = ""

        return (f"{prefix}{msg}", kwargs)


class LoggerConfigError(Exception):
    """
    Exception raised when a configuration error is detected
    """


def setup_logger(log_file, log_level, quiet, log_rotate=None, log_rotate_arg=None):
    """
    Setups the logging based on ``log_file``, ``log_level``, ``quiet``.

    :param str log_file: the log file, ``"stderr"`` or ``"stdout"``
    :param int log_level: a log level
    :param bool quiet: If set to ``True``, then logging is suppressed
    :param str log_rotate: the type of rotation, ``"time"`` or ``"size"``
    :param str log_rotate_arg: rotation arguments
    :raise LoggerConfigError: when the settings are incorrect
    """
    fmt = "%(asctime)s[%(process)d] %(levelname)-8s %(name)s:%(lineno)d - %(message)s"

    formatter = {"format": fmt}
    if quiet:
        root = logging.getLogger("")
        root.addHandler(logging.NullHandler())
        return

    if log_file in ("stderr", "stdout"):
        handler = {
            "level": log_level,
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": getattr(sys, log_file),
        }
    else:
        if log_rotate in ("size", "time"):
            if log_rotate_arg is None:
                raise LoggerConfigError("No rotation arguments passed")

            if log_rotate == "size":
                m = re.match(r"([0-9]+)([kmgKMG]?)$", log_rotate_arg)
                if m is None:
                    raise LoggerConfigError(
                        f"Invalid rotate argument {log_rotate_arg!r}"
                    )

                rotate_size, rotate_mult = m.groups()
                rotate_size = int(rotate_size)
                rotate_mult = rotate_mult.upper()
                mult_dict = {"": 1, "K": 2 ** 10, "M": 2 ** 20, "G": 2 ** 30}
                rotate_size *= mult_dict[rotate_mult]
                handler = {
                    "level": log_level,
                    "formatter": "standard",
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": log_file,
                    "maxBytes": rotate_size,
                    "backupCount": 5,
                }
            else:
                m = re.match(r"([0-9]+:)?([SMHD]|W[0-6]|midnight)$", log_rotate_arg)
                if m is None:
                    raise LoggerConfigError(
                        f"Invalid rotate argument {log_rotate_arg!r}"
                    )

                interval, when = m.groups()
                if interval is None:
                    interval = 1
                else:
                    interval = int(interval[0:-1])

                handler = {
                    "level": log_level,
                    "formatter": "standard",
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "filename": log_file,
                    "when": when,
                    "interval": interval,
                    "backupCount": 5,
                }
        else:
            handler = {
                "level": log_level,
                "formatter": "standard",
                "class": "logging.FileHandler",
                "filename": log_file,
            }

    logging_conf = {
        "version": 1,
        "formatters": {"standard": formatter},
        "handlers": {
            "hdl": handler,
        },
        "loggers": {
            # root logger
            "": {
                "handlers": ["hdl"],
                "level": log_level,
            },
        },
        "disable_existing_loggers": False,
    }

    logging.config.dictConfig(logging_conf)

    # silencing some "noisy" modules
    logging.getLogger("parso").setLevel(logging.CRITICAL + 1)
    logging.getLogger("asyncio").setLevel(logging.CRITICAL + 1)
