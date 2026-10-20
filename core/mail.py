import logging
from threading import Thread

from django.conf import settings
from django.db import connection


logger = logging.getLogger(__name__)


def run_in_background(function, *args):
    """Run `function(*args)` without blocking the request.

    In production this uses a daemon thread (Render stays up, so it finishes).
    Tests and local development run it inline. Errors are logged, never raised,
    because a failed notification must not break the page that triggered it.
    """

    def target():
        try:
            function(*args)
        except Exception:
            logger.exception("Background task %s failed", getattr(function, "__name__", function))
        finally:
            if settings.ENQUIRY_EMAIL_ASYNC:
                # The thread owns its own DB connection; release it (Neon has few slots).
                connection.close()

    if settings.ENQUIRY_EMAIL_ASYNC:
        Thread(target=target, daemon=True).start()
    else:
        target()
