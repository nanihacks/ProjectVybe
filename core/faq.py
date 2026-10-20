from django.conf import settings
from django.core.cache import cache

from .models import Faq


FAQ_CACHE_KEY = "published_faqs"
PLACEMENTS = {"home", "projects", "services", "contact", "courses"}


def _all_published():
    return cache.get_or_set(
        FAQ_CACHE_KEY,
        lambda: list(Faq.objects.filter(is_published=True)),
        settings.FAQ_CACHE_SECONDS,
    )


def faqs_for(placement):
    """Published FAQs ticked for `placement` ("home", "projects", "services", "contact", "courses")."""
    if placement not in PLACEMENTS:
        raise ValueError(f"Unknown FAQ placement: {placement}")
    return [faq for faq in _all_published() if getattr(faq, f"show_on_{placement}")]


def clear_faq_cache(**kwargs):
    cache.delete(FAQ_CACHE_KEY)
