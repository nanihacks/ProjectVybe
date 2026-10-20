import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from .ratelimit import client_ip


logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
FORM_FIELD = "cf-turnstile-response"
FAILURE_MESSAGE = "Please complete the security check and try again."


def is_enabled():
    """Turnstile is off until both keys are configured (local dev and tests)."""
    return bool(settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def verify(token, ip=""):
    """Ask Cloudflare whether `token` is a valid solved challenge.

    A definite "no" returns False. If Cloudflare cannot be reached the visitor is
    let through (the honeypot and rate limits still apply) because losing a real
    enquiry is worse than letting a bot past a single layer.
    """
    if not is_enabled():
        return True
    if not token:
        return False

    payload = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if ip:
        payload["remoteip"] = ip
    request = Request(VERIFY_URL, data=urlencode(payload).encode(), method="POST")
    try:
        with urlopen(request, timeout=5) as response:
            return bool(json.load(response).get("success"))
    except (URLError, OSError, ValueError):
        logger.warning("Turnstile verification unavailable; letting the request through")
        return True


def request_passes(request):
    """True when Turnstile is off, or the request carries a valid solved token."""
    return verify(request.POST.get(FORM_FIELD, ""), client_ip(request))
