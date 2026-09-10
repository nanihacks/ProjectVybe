import json
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder


def site_origin():
    """Return the configured public origin without paths or trailing slashes."""
    configured_url = str(getattr(settings, "SITE_URL", "")).strip()
    parsed_url = urlsplit(configured_url)

    if parsed_url.scheme and parsed_url.netloc:
        return urlunsplit((parsed_url.scheme, parsed_url.netloc, "", "", "")).rstrip("/")

    return configured_url.rstrip("/")


def absolute_url(path="/"):
    """Build a URL from SITE_URL without trusting the request Host header."""
    normalized_path = str(path or "/").lstrip("/")
    return f"{site_origin()}/{normalized_path}"


def site_scheme():
    return urlsplit(site_origin()).scheme or "https"


def json_ld_string(data):
    """Serialize JSON-LD safely for an application/ld+json script element."""
    return (
        json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
