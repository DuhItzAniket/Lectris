"""The errors LECTRIS raises."""


class LectrisError(Exception):
    """The base of every error LECTRIS raises on purpose."""


class FormatError(LectrisError):
    """An input a reader cannot read: the wrong format, or a malformed document."""
