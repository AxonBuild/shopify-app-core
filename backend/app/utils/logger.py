"""Shared logger helpers for the application.

Usage::

    from app.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("something happened", extra={"shop": shop})
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a stdlib logger for the given *name*.

    All loggers share the root configuration set up in ``main.py``.
    Using ``__name__`` as the name gives you hierarchical filtering, e.g.::

        LOG_LEVEL=DEBUG      -> all messages
        LOG_LEVEL=INFO       -> info and above
    """
    return logging.getLogger(name)
