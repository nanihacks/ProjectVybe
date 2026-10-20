def cloudinary_url(field, width=None):
    """Return a resized, auto-format Cloudinary URL for an image field.

    Callers should stick to a few fixed widths (96, 240, 640, 1200) so the
    free Cloudinary plan stays within its transformation credits.
    """
    if not field:
        return ""
    try:
        if width and getattr(field, "public_id", None) and hasattr(field, "build_url"):
            try:
                return field.build_url(
                    secure=True,
                    transformation={
                        "width": width,
                        "crop": "limit",
                        "quality": "auto",
                        "fetch_format": "auto",
                    },
                )
            except (AttributeError, ValueError):
                pass
        return field.url
    except (AttributeError, ValueError):
        return ""
