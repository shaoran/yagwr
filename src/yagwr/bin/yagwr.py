import sys
import logging
import argparse
import time
import yaml

from http.server import ThreadingHTTPServer

from .. import __version__
from ..logger import setup_logger, LoggerConfigError
from ..webhooks import WebhookHandler, process_gitlab_request_task
from ..async_in_thread import AsyncInThread
from ..checker import InvalidExpression
from ..rules import Rule

log = logging.getLogger("yagwr")


def create_cmdline_parse():
    """
    Helper function that creates the command line arguments

    :return: a command line argument
    :rtype: argparse.ArgumentParser
    """
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
        "--log-level", help="the log level", default="INFO", choices=_level_choices
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

    parser.add_argument(
        "rules",
        metavar="<RULE FILE>",
        help="A YAML file with the rules",
        type=argparse.FileType("r"),
    )

    return parser


def main(argv=sys.argv[1:]):
    parser = create_cmdline_parse()

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

    log.info("Reading %r", args.rules.name)
    rules_raw = yaml.safe_load(args.rules)
    args.rules.close()

    if isinstance(rules_raw, dict):
        rules_raw = [rules_raw]

    rules = []

    log.info("Parsing rules")
    for idx, rule_raw in enumerate(rules_raw):
        try:
            rule = Rule.from_dict(rule_raw)
        except InvalidExpression as e:
            log.error("Rule number %d is invalid: %s", idx + 1, str(e))
            continue
        except:
            log.error("Rule number %d could not be parsed", idx + 1, exc_info=True)
            continue

        rules.append(rule)

    if not rules:
        log.error("After parsing no rules were found")
        return

    # used by the HTTP server and main asyncio task to
    # synchronize with each other
    controller = {
        "loop": None,
        "queue": None,
        "rules": rules,
    }

    async_thread = AsyncInThread(process_gitlab_request_task(controller))

    log.info("Starting asyncio thread and wait for initialization")

    async_thread.start()

    while True:
        if controller["loop"] and controller["queue"]:
            break
        time.sleep(0.1)

    try:
        server_addr = (args.host, args.port)
        log.info("Listenting on %s:%d", *server_addr)
        http_server = ThreadingHTTPServer(server_addr, WebhookHandler)
        http_server._controller = controller

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
            log.debug("Stopping HTTP server")
            http_server.server_close()
    finally:
        log.debug("Stopping asyncio thread")
        async_thread.stop()

    return res
