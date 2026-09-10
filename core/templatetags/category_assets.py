from django import template
from django.templatetags.static import static


register = template.Library()

LOCAL_CATEGORY_LOGOS = {
    "ai-machine-learning": "images/categories/ai-machine-learning.png",
    "cybersecurity": "images/categories/cybersecurity.png",
    "data-science": "images/categories/data-science.png",
    "iot-embedded-systems": "images/categories/iot-embedded-systems.png",
    "mobile-applications": "images/categories/mobile-applications.png",
    "web-development": "images/categories/web-development.png",
}


@register.simple_tag
def category_logo_url(category):
    """Prefer a category's identity image and fall back to local UI assets."""
    return _cloudinary_image_url(category, "image") or _local_category_logo(category)


@register.simple_tag
def category_home_image_url(category):
    """Prefer the homepage image, then the category identity image or local asset."""
    return (
        _cloudinary_image_url(category, "homepage_image")
        or _cloudinary_image_url(category, "image")
        or _local_category_logo(category)
    )


def _cloudinary_image_url(category, field_name):
    image = getattr(category, field_name, None)
    if image:
        try:
            if image.url:
                return image.url
        except (AttributeError, ValueError):
            pass


def _local_category_logo(category):
    asset_path = LOCAL_CATEGORY_LOGOS.get(getattr(category, "slug", ""), "")
    return static(asset_path) if asset_path else ""
