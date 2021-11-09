import sys
import logging
import argparse

from http.server import ThreadingHTTPServer

from .. import __version__
from ..logger import setup_logger, LoggerConfigError
from ..webhooks import WebhookHandler

log = logging.getLogger("yagwr")


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='Yat Another Gitlab Webhooks Runner',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=False,
    )

    server_group = parser.add_argument_group(
        "Server", "These options control the webserver connection"
    )

    server_group.add_argument("--host", help="listen to host", default="0.0.0.0")
    server_group.add_argument(
        "-p", "--port", help="listen to port", default=7777, type=int
    )

    log_group = parser.add_argument_group(
        "Logging", "These options control the logging behaviour"
    )

    log_group.add_argument(
        "--log-file",
        help="logfile, use 'stdout', 'stdout' to write logs to 'stdout' and 'stderr'",
        default="stderr",
    )

    _level_choices = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    log_group.add_argument(
        "--log-level", help="the log level", default="WARNING", choices=_level_choices
    )

    log_group.add_argument(
        "--log-rotate",
        help="Rotate the log file by size of day, does not apply to 'stdout' nor 'stderr'",
        choices=("size", "time"),
        default="size",
    )

    log_group.add_argument(
        "--log-rotate-arg",
        help="The size of the file (with prefix like 1k or 1m) or then '[interval:]when' "
        "parameters of TimedRotatingFileHandler, for example 'midnight' or '3:H', interval=1 is the default",
    )

    log_group.add_argument(
        "-q",
        "--quiet",
        help="run in silent mode, no log outputs are generated",
        action="store_true",
        default=False,
    )

    parser.add_argument("--help", help="show this help message and exit", action="help")
    parser.add_argument(
        "-v", '--version', action='version', version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args(argv)

    try:
        setup_logger(
            args.log_file,
            args.log_level,
            args.quiet,
            log_rotate=args.log_rotate,
            log_rotate_arg=args.log_rotate_arg,
        )
    except LoggerConfigError as e:
        parser.error(f"Unable to setup the logger: {e.args[0]}")

    if args.port < 1:
        parser.error(f"Invalid portb {args.port!r}, only positive values are permitted")

    server_addr = (args.host, args.port)
    log.info("Listenting on %s:%d", *server_addr)
    http_server = ThreadingHTTPServer(server_addr, WebhookHandler)

    res = 0
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        # cosmetic reasons, don't display this exception
        pass
    except:
        log.error("The HTTP server terminated with an error", exc_info=True)
        res = 1
    finally:
        http_server.server_close()

    return res
