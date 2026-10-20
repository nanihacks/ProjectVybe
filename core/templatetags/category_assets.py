from django import template
from django.templatetags.static import static

from core.images import cloudinary_url


register = template.Library()

LOCAL_CATEGORY_SLUGS = {
    "ai-machine-learning",
    "cybersecurity",
    "data-science",
    "iot-embedded-systems",
    "mobile-applications",
    "web-development",
}

# Fixed widths keep the number of Cloudinary transformations small (free plan).
ICON_WIDTH = 96
CARD_WIDTH = 640


@register.simple_tag
def category_logo_url(category):
    """Small icon for navigation: Cloudinary image, else a local 96px asset."""
    return _cloudinary_image_url(category, "image", ICON_WIDTH) or _local_category_logo(
        category, "images/categories/icons/{slug}.webp"
    )


@register.simple_tag
def category_card_image_url(category):
    """Card-size category image: Cloudinary image, else the local 640px asset."""
    return _cloudinary_image_url(category, "image", CARD_WIDTH) or _local_category_logo(
        category, "images/categories/{slug}.webp"
    )


@register.simple_tag
def category_home_image_url(category):
    """Card image: homepage image, then the category image, then a local asset."""
    return (
        _cloudinary_image_url(category, "homepage_image", CARD_WIDTH)
        or _cloudinary_image_url(category, "image", CARD_WIDTH)
        or _local_category_logo(category, "images/categories/{slug}.webp")
    )


def _cloudinary_image_url(category, field_name, width):
    image = getattr(category, field_name, None)
    if image:
        return cloudinary_url(image, width=width)
    return ""


def _local_category_logo(category, path_template):
    slug = getattr(category, "slug", "")
    return static(path_template.format(slug=slug)) if slug in LOCAL_CATEGORY_SLUGS else ""
