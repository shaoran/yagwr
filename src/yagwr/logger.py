import logging


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
