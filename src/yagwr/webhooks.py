import asyncio
import logging
import re
from http.server import BaseHTTPRequestHandler

from .logger import NamedLogger

raw_log = logging.getLogger(__name__)

log = NamedLogger(raw_log, {"name": "HTTPD"})

# https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#http-responses-for-your-endpoint


class WebhookHandler(BaseHTTPRequestHandler):
    """
    The request handler for Gitlab webhooks

    The `Gitlab documentation <https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#http-responses-for-your-endpoint>`_
    states:

        Your endpoint should send its HTTP response as fast as possible. If the response
        takes longer than the configured timeout, GitLab assumes the hook failed and retries it.


    For this reason this request handler pushes the request information (headers, payload) onto a
    :py:class:`asyncio.Queue` queue and responds as fast as possible. This approach is fine because
    the documentation also says:

        GitLab ignores the HTTP status code returned by your endpoint.

    Hence it doesn't matter whether the processing takes a long time or even fails.

    The processing itself is executed in a ``asyncio`` task.
    """

    def finish_request(self):
        """
        Helper that finished the request
        """
        self.send_response(200, message="OK")
        self.end_headers()

    def do_POST(self):
        """
        Handles the HTTP request from gitlab
        """
        request = {
            "client_address": self.client_address,
            "path": self.path,
            "request": self.requestline,
            "headers": dict(self.headers),
            "body": None,
        }

        log.debug("Parsing incoming request from %s", self.client_address[0])

        header_length = self.headers["Content-Length"]
        if header_length is not None:
            request["body"] = self.rfile.read(int(header_length))

        if hasattr(self.server, "_controller"):
            try:
                loop = self.server._controller["loop"]
                queue = self.server._controller["queue"]
            except KeyError:
                log.error(
                    "Invalid controller object, cannot put into queue", exc_info=True
                )
                return self.finish_request()

            log.debug("Pushing request data into asyncio queue")
            try:
                loop.call_soon_threadsafe(lambda: queue.put_nowait(request))
            except:
                log.error("Unable to push request into asyncio queue", exc_info=True)

        self.finish_request()

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


async def process_gitlab_request_task(controller):
    """
    Main asyncio tasks that reads the requests from the queue and
    launches the processing of the queue
    """
    log = NamedLogger(raw_log, {"name": "PROCESS"})

    log.debug("Starting request worker")

    log.info("Generating asyncio queue")
    queue = asyncio.Queue()

    controller["loop"] = asyncio.get_running_loop()
    controller["queue"] = queue

    while True:
        request = await queue.get()
        queue.task_done()

        headers = request.get("headers") or {}

        data_dict = {
            "path": request.get("path"),
            "gitlab_token": headers.get("X-Gitlab-Token"),
            "gitlab_event": headers.get("X-Gitlab-Event"),
            "gitlab_host": headers.get("Host"),
        }

        rules = controller.get("rules") or []

        for idx, rule in enumerate(rules):
            try:
                match = rule.matches(data_dict)
            except:
                log.error("Rule evaluation for rule %d", idx + 1)
                continue

            if rule.matches(data_dict):
                try:
                    await execute_action(request, rule.action, log)
                except asyncio.CancelledError:
                    raise
                except:
                    log.error(
                        "Unable to execute action of rule %d", idx + 1, exc_info=True
                    )


async def execute_action(request, action, log):
    """
    Helper function that executes arbitrary commands
    """
    transform_key = lambda key: re.sub(r"[\s-]", "_", key)

    headers = request.get("headers") or {}
    env = {"YAGWR_" + transform_key(key): str(value) for key, value in headers.items()}

    log.debug("Creating subprocess")
    proc = await asyncio.create_subprocess_shell(
        action,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    log.debug("Writing stdin with payload")
    log.debug("Command: %r", action)
    stdout, stderr = await proc.communicate(input=request.get("body"))
    log.debug("return code: %s", proc.returncode)
    stdout = stdout.decode("UTF-8", errors="ignore").strip()
    stderr = stderr.decode("UTF-8", errors="ignore").strip()

    if stdout:
        log.debug("STDOUT:\n%s", stdout)
    if stderr:
        log.debug("STDERR:\n%s", stderr)

    if proc.returncode != 0:
        try:
            body = request["body"]
            if isinstance(body, bytes):
                body = body.decode("UTF-8", errors="ignore").strip()
            else:
                body = f"Unknown payload type: {body!r}"

            log.debug("command failed, payload was\n%s\n----\n", body)
        except KeyError:
            pass
