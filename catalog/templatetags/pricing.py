from decimal import Decimal, InvalidOperation

from django import template

from catalog.pricing import format_inr


register = template.Library()


@register.filter
def inr(value):
    """Show an amount in rupees with Indian digit grouping, e.g. ₹1,24,999."""
    if value in (None, ""):
        return ""
    try:
        return format_inr(Decimal(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
