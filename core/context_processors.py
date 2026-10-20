from django.conf import settings
from django.core.cache import cache

from catalog.models import Category

from legal.services import footer_links

from .images import cloudinary_url
from .seo import absolute_url, site_origin
from .site import get_site_settings
from .turnstile import is_enabled as turnstile_enabled


def _whatsapp_chat_url(site_settings):
    """wa.me link from the number in Site Settings (or the server setting), without another query."""
    from re import sub

    number = sub(r"\D", "", site_settings.whatsapp_number or settings.WHATSAPP_NUMBER or "")
    return f"https://wa.me/{number}" if number else ""


NAVIGATION_CATEGORIES_CACHE_KEY = "navigation_categories"


def _navigation_categories():
    return cache.get_or_set(
        NAVIGATION_CATEGORIES_CACHE_KEY,
        lambda: list(Category.objects.filter(is_active=True).order_by("name")),
        settings.NAVIGATION_CATEGORIES_CACHE_SECONDS,
    )


def public_site_config(request):
    url_name = getattr(getattr(request, "resolver_match", None), "url_name", None)
    site_settings = get_site_settings(request)
    navigation_categories = None
    if url_name not in {"about", "project_catalogue"}:
        navigation_categories = _navigation_categories()

    return {
        "site_settings": site_settings,
        "legal_footer_links": footer_links(),
        "public_contact_email": site_settings.contact_email or settings.PUBLIC_CONTACT_EMAIL,
        "default_og_image_url": cloudinary_url(site_settings.share_image, width=1200),
        "site_name": settings.SITE_NAME,
        "site_description": settings.SITE_DESCRIPTION,
        "site_url": site_origin(),
        "navigation_categories": navigation_categories,
        "whatsapp_chat_url": _whatsapp_chat_url(site_settings),
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY if turnstile_enabled() else "",
        "canonical_url": absolute_url(request.path),
        "robots_directive": "index, follow",
    }
