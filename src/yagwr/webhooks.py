import logging

from http.server import BaseHTTPRequestHandler

from .logger import NamedLogger

raw_log = logging.getLogger(__name__)

log = NamedLogger(raw_log, {"name": "HTTPD"})

# https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#http-responses-for-your-endpoint


class WebhookHandler(BaseHTTPRequestHandler):
    """
    The request handler for Gitlab webhooks

    The `Gitlab documentation <https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#http-responses-for-your-endpoint>`
    metions says::

        Your endpoint should send its HTTP response as fast as possible. If the response
        takes longer than the configured timeout, GitLab assumes the hook failed and retries it.


    For this reason this request handler pushes the request information (headers, payload) onto a
    :py:class:`asyncio.Queue` queue and responds as fast as possible. This approach is fine because
    the documentation also says::

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
        request = {
            "client_address": self.client_address,
            "path": self.path,
            "request": self.requestline,
            "headers": dict(self.headers),
            "body": None,
        }

        log.debug("Parsing incoming request from %s", self.client_address[0])

        header_length = self.headers['Content-Length']
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
