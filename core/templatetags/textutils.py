from django import template


register = template.Library()


@register.filter
def split_dots(value):
    """'AI/ML · Web · Security' -> ['AI/ML', 'Web', 'Security'] (also accepts | and , as separators)."""
    text = str(value or "")
    for separator in ("|", ","):
        text = text.replace(separator, "·")
    return [part.strip() for part in text.split("·") if part.strip()]


@register.filter
def initial(value):
    """First letter of a name, for avatar circles."""
    value = str(value or "").strip()
    return value[:1].upper()
