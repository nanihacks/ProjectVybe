import logging

from django.conf import settings
from django.core.mail import get_connection
from django.urls import reverse

from core.email_render import build_email
from core.mail import run_in_background
from core.site import contact_email

from .models import CourseWaitlistEntry


logger = logging.getLogger(__name__)


def build_waitlist_emails(entry, owner):
    """(visitor_message, owner_message_or_None). Visitor text is fixed: nothing typed is echoed."""
    from_email = settings.DEFAULT_FROM_EMAIL or owner
    about = f" for {entry.course.title}" if entry.course else " for new courses"
    visitor = build_email(
        f"You're on the ProjectVybe waitlist{about}",
        {
            "heading": "You're on the list",
            "preheader": "We'll email you when it opens.",
            "greeting": "Hello,",
            "paragraphs": [
                f"Thank you. We have added you to the waitlist{about}, and we will email you when there is news.",
                f"Your reference is {entry.reference}. If you did not ask for this, you can ignore this email.",
            ],
        },
        to=[entry.email],
        from_email=from_email,
        reply_to=[owner] if owner else None,
    )
    owner_message = None
    if owner:
        owner_message = build_email(
            f"New waitlist sign-up {entry.reference}: {entry.course.title if entry.course else 'any course'}",
            {
                "heading": f"New waitlist sign-up {entry.reference}",
                "details": [
                    ("Course", entry.course.title if entry.course else "Any new course"),
                    ("Name", entry.name),
                    ("Email", entry.email),
                    ("Phone", entry.phone or "not given"),
                ],
                "button_url": f"{settings.SITE_URL}{reverse('admin:courses_coursewaitlistentry_change', args=[entry.pk])}",
                "button_label": "Open in Admin",
                "footnote": "Sent to you because you receive waitlist sign-ups for this website.",
            },
            to=[owner],
            from_email=from_email,
            reply_to=[entry.email],
        )
    return visitor, owner_message


def send_waitlist_emails(entry_id):
    entry = CourseWaitlistEntry.objects.select_related("course").filter(pk=entry_id).first()
    if entry is None:
        return
    visitor, owner_message = build_waitlist_emails(entry, contact_email())
    connection = get_connection(fail_silently=False)
    for message in [visitor] + ([owner_message] if owner_message else []):
        message.connection = connection
        try:
            message.send(fail_silently=False)
        except Exception:
            logger.exception("Unable to send waitlist email %s", message.subject)


def queue_waitlist_emails(entry):
    run_in_background(send_waitlist_emails, entry.pk)
