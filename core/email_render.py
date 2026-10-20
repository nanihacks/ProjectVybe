"""Branded multipart emails: a plain-text body plus an HTML alternative from one context."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.templatetags.static import static
from django.template.loader import render_to_string

from .site import contact_email, get_site_settings


BRAND = {
    "primary": "#3346c8",
    "text": "#122033",
    "muted": "#526276",
    "border": "#d8e1ed",
    "background": "#eef3f9",
    "navy": "#0f1b33",
}


def _shared_context():
    try:
        tagline = get_site_settings().footer_tagline
    except Exception:
        tagline = "Build. Learn. Grow."
    return {
        "brand": BRAND,
        "site_url": settings.SITE_URL,
        "logo_url": f"{settings.SITE_URL}{static('images/brand/projectvybe-logo-email.png')}",
        "contact_email": contact_email(),
        "footer_tagline": tagline,
        "site_name": settings.SITE_NAME,
    }


def render_email(template, context):
    """(text, html) for emails/<template>.txt and .html with the shared brand context."""
    full = {**_shared_context(), **context}
    return (
        render_to_string(f"emails/{template}.txt", full).strip() + "\n",
        render_to_string(f"emails/{template}.html", full),
    )


def build_email(subject, context, to, from_email, reply_to=None, template="message"):
    """An EmailMultiAlternatives ready to send. Subject newlines are removed (header safety)."""
    text, html = render_email(template, context)
    message = EmailMultiAlternatives(
        subject=" ".join(str(subject).split()),
        body=text,
        from_email=from_email,
        to=to,
        reply_to=reply_to or None,
    )
    message.attach_alternative(html, "text/html")
    return message
