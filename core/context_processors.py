from django.conf import settings

from catalog.models import Category

from .seo import absolute_url, site_origin


def public_site_config(request):
    url_name = getattr(getattr(request, "resolver_match", None), "url_name", None)
    navigation_categories = None
    if url_name not in {"about", "project_catalogue"}:
        navigation_categories = Category.objects.filter(is_active=True).order_by("name")

    return {
        "public_contact_email": settings.PUBLIC_CONTACT_EMAIL,
        "site_name": settings.SITE_NAME,
        "site_description": settings.SITE_DESCRIPTION,
        "site_url": site_origin(),
        "navigation_categories": navigation_categories,
        "canonical_url": absolute_url(request.path),
        "robots_directive": "index, follow",
    }
