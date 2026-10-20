import logging

from django.conf import settings


logger = logging.getLogger(__name__)


def get_site_settings(request=None):
    """The single SiteSettings row, looked up once per request."""
    from .models import SiteSettings

    if request is not None:
        cached = getattr(request, "_site_settings", None)
        if cached is not None:
            return cached
    site_settings = SiteSettings.get_solo()
    if request is not None:
        request._site_settings = site_settings
    return site_settings


def _setting(field, fallback):
    """Admin value if set, else the server setting. Never breaks on a database error."""
    try:
        value = getattr(get_site_settings(), field)
    except Exception:
        logger.exception("Could not read site settings; using server setting for %s", field)
        value = ""
    return (value or fallback or "").strip()


def contact_email():
    """Address that receives enquiries and admin alerts."""
    return _setting("contact_email", settings.PUBLIC_CONTACT_EMAIL)


def whatsapp_number():
    return _setting("whatsapp_number", settings.WHATSAPP_NUMBER)
