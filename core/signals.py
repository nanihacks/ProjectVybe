import logging

from axes.signals import user_locked_out
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.dispatch import receiver
from django.utils import timezone

from .mail import run_in_background
from .ratelimit import client_ip
from .site import contact_email


logger = logging.getLogger(__name__)

# One lockout email per IP per hour, however many blocked attempts follow.
LOCKOUT_ALERT_SECONDS = 3600


def _send_alert(subject, body):
    recipient = contact_email()
    if not recipient:
        return
    EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL or recipient,
        to=[recipient],
    ).send(fail_silently=False)


def _describe(request, username):
    now = timezone.localtime().strftime("%d %b %Y, %H:%M:%S %Z")
    ip = client_ip(request) if request is not None else "unknown"
    agent = _clean(request.META.get("HTTP_USER_AGENT", "") if request is not None else "", 200)
    return f"User: {username}\nTime: {now}\nIP address: {ip}\nBrowser: {agent or 'unknown'}"


@receiver(user_logged_in)
def alert_on_staff_login(sender, request, user, **kwargs):
    if not user.is_staff:
        return
    run_in_background(
        _send_alert,
        "ProjectVybe admin login",
        "A staff member signed in to ProjectVybe Admin.\n\n"
        + _describe(request, user.get_username())
        + "\n\nIf this was not you, lock the account and change the password.",
    )


def _clean(value, limit=80):
    """Drop control characters (newlines, etc.) from attacker-supplied text before logging or emailing."""
    return "".join(ch for ch in str(value or "") if ch.isprintable())[:limit]


@receiver(user_locked_out)
def alert_on_lockout(sender, request=None, username=None, ip_address=None, **kwargs):
    # Failed attempts are only logged by axes; email once when an IP gets locked out.
    if not cache.add(f"alert:lockout:{ip_address}", 1, LOCKOUT_ALERT_SECONDS):
        return
    username = _clean(username)
    logger.warning("Admin login locked out for IP %s (user %s)", _clean(ip_address), username)
    run_in_background(
        _send_alert,
        "ProjectVybe admin lockout",
        "Too many failed admin login attempts. This IP is locked out for one hour.\n\n"
        + _describe(request, username or "unknown"),
    )


from django.db.models.signals import post_delete, post_save  # noqa: E402

from .faq import clear_faq_cache  # noqa: E402
from .models import Faq  # noqa: E402

post_save.connect(clear_faq_cache, sender=Faq, dispatch_uid="clear_faq_cache_save")
post_delete.connect(clear_faq_cache, sender=Faq, dispatch_uid="clear_faq_cache_delete")
