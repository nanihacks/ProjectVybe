from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.context_processors import NAVIGATION_CATEGORIES_CACHE_KEY

from .models import Category


@receiver([post_save, post_delete], sender=Category)
def clear_navigation_categories_cache(sender, **kwargs):
    cache.delete(NAVIGATION_CATEGORIES_CACHE_KEY)
