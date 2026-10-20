from django.conf import settings
from django.core.cache import cache

from .models import LegalPage

FOOTER_LINKS_CACHE_KEY = "legal_footer_links"
PRIVACY_SLUG = "privacy-policy"


def published_pages():
    """Published pages that have at least one published version."""
    return LegalPage.objects.filter(is_published=True, versions__isnull=False).distinct()


def get_public_page(slug):
    """(page, latest version) for a page visitors may see, else (None, None)."""
    page = LegalPage.objects.filter(slug=slug, is_published=True).first()
    version = page.latest_version if page else None
    if version is None:
        return None, None
    return page, version


def current_privacy_version():
    """The Privacy Policy version visitors currently see, or None."""
    return get_public_page(PRIVACY_SLUG)[1]


def footer_links():
    """[(label, url)] for the footer, cached and cleared when pages change."""

    def build():
        pages = published_pages().filter(show_in_footer=True).order_by("footer_order", "title")
        return [(page.footer_text, page.get_absolute_url()) for page in pages]

    return cache.get_or_set(FOOTER_LINKS_CACHE_KEY, build, settings.LEGAL_FOOTER_CACHE_SECONDS)
