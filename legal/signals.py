from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import LegalPage, LegalPageVersion
from .services import FOOTER_LINKS_CACHE_KEY


@receiver([post_save, post_delete], sender=LegalPage)
@receiver([post_save, post_delete], sender=LegalPageVersion)
def clear_footer_links_cache(sender, **kwargs):
    cache.delete(FOOTER_LINKS_CACHE_KEY)
