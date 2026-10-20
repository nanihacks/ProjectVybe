import logging
from email.utils import formataddr, parseaddr
from re import sub
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import get_connection
from django.urls import reverse

from core.email_render import build_email
from core.mail import run_in_background
from core.site import contact_email, whatsapp_number


logger = logging.getLogger(__name__)


def whatsapp_enquiry_url(message):
    number = sub(r"\D", "", whatsapp_number())
    if not number:
        return ""
    return f"https://wa.me/{number}?{urlencode({'text': message})}"


def build_enquiry_message(lead):
    """Plain-text summary of a saved lead (owner email and WhatsApp prefill)."""
    lines = ["Hello ProjectVybe,", ""]

    if lead.project:
        lines.extend([f"I am interested in the {lead.project.title} project.", ""])
    else:
        lines.append("I would like to make an enquiry.")

    lines.append(f"Reference: {lead.reference}")
    if lead.name:
        lines.append(f"Name: {lead.name}")
    if lead.email:
        lines.append(f"Email: {lead.email}")
    if lead.phone:
        lines.append(f"Phone: {lead.phone}")

    additional_services = [
        item.name
        for item in [*lead.selected_services.all(), *lead.selected_addons.all()]
    ]
    if additional_services:
        lines.extend(["", "Additional services:", ", ".join(additional_services)])

    if lead.message:
        lines.extend(["", f"Message: {lead.message}"])

    return "\n".join(lines)


def _sender_address():
    """Bare address from DEFAULT_FROM_EMAIL, falling back to the contact email."""
    return parseaddr(settings.DEFAULT_FROM_EMAIL)[1] or contact_email()


def _clean_display_name(value):
    return " ".join(value.split())[:60]


def _admin_link(route, pk):
    return f"{settings.SITE_URL}{reverse(route, args=[pk])}"


def _owner_message(lead, recipient):
    title = lead.project.title if lead.project else "General enquiry"
    subject = f"New enquiry {lead.reference}: {title} – {_clean_display_name(lead.name)}"
    # formataddr encodes the name, so control characters cannot inject headers.
    from_email = formataddr(
        (f"{_clean_display_name(lead.name)} via ProjectVybe", _sender_address())
    )
    extras = ", ".join(
        item.name for item in [*lead.selected_services.all(), *lead.selected_addons.all()]
    )
    details = [
        ("Reference", lead.reference),
        ("Name", lead.name),
        ("Email", lead.email),
        ("Phone", lead.phone),
        ("Project", lead.project.title if lead.project else "General enquiry"),
        ("Add-ons / services", extras),
        ("Message", lead.message),
    ]
    return build_email(
        subject,
        {
            "heading": f"New enquiry {lead.reference}",
            "preheader": f"{lead.name} sent an enquiry about {title}.",
            "paragraphs": ["Someone sent an enquiry on the website. Reply to this email to answer them."],
            "details": [(label, value) for label, value in details if value],
            "button_url": _admin_link("admin:leads_lead_change", lead.pk),
            "button_label": "Open in Admin",
            "footnote": "Sent to you because you receive enquiries for this website.",
        },
        to=[recipient],
        from_email=from_email,
        reply_to=[lead.email] if lead.email else None,
    )


def _confirmation_message(lead, recipient):
    # Fixed template: nothing the visitor typed is echoed back to them.
    about = f" about {lead.project.title}" if lead.project else ""
    whatsapp = whatsapp_enquiry_url(f"Hello ProjectVybe, my enquiry reference is {lead.reference}.")
    return build_email(
        f"We received your ProjectVybe enquiry ({lead.reference})",
        {
            "heading": "We received your enquiry",
            "preheader": f"Your reference is {lead.reference}.",
            "greeting": "Hello,",
            "paragraphs": [
                f"Thank you for contacting ProjectVybe. We have received your enquiry{about} and will get back to you soon.",
                f"Your reference number is {lead.reference}. Please quote it if you contact us again.",
                "If you did not make this enquiry, you can ignore this email or reply to tell us.",
            ],
            "button_url": whatsapp,
            "button_label": "Continue on WhatsApp",
        },
        to=[lead.email],
        from_email=settings.DEFAULT_FROM_EMAIL or recipient,
        reply_to=[recipient],
    )


def send_privacy_request_emails(request_id):
    """Tell the owner about a privacy request and acknowledge it to the requester."""
    from .models import PrivacyRequest

    recipient = contact_email()
    privacy_request = PrivacyRequest.objects.filter(pk=request_id).first()
    if privacy_request is None or not recipient:
        return

    connection = get_connection(fail_silently=False)
    number = privacy_request.request_number
    from_email = settings.DEFAULT_FROM_EMAIL or recipient
    owner_message = build_email(
        f"Privacy request {number}: {privacy_request.get_kind_display()}",
        {
            "heading": f"Privacy request {number}",
            "paragraphs": [
                "A privacy request was submitted on the website. Check that the person owns this "
                "address before acting."
            ],
            "details": [
                ("Request", number),
                ("Type", privacy_request.get_kind_display()),
                ("Email given", privacy_request.email),
                ("Enquiry reference", privacy_request.reference or "none given"),
                ("Message", privacy_request.message or "none"),
            ],
            "button_url": _admin_link("admin:leads_privacyrequest_change", privacy_request.pk),
            "button_label": "Open in Admin",
            "footnote": "Sent to you because you receive privacy requests for this website.",
        },
        to=[recipient],
        from_email=from_email,
        reply_to=[privacy_request.email],
    )
    # Fixed text only: nothing the requester typed is echoed back to them.
    acknowledgement = build_email(
        f"We received your privacy request ({number})",
        {
            "heading": "We received your privacy request",
            "preheader": f"Your request number is {number}.",
            "greeting": "Hello,",
            "paragraphs": [
                f"We have received your privacy request ({number}). We will check your details and "
                "reply to this address, and aim to complete the request within one month.",
                "If you did not make this request, you can ignore this email.",
            ],
        },
        to=[privacy_request.email],
        from_email=from_email,
        reply_to=[recipient],
    )
    for message in (owner_message, acknowledgement):
        message.connection = connection
        try:
            message.send(fail_silently=False)
        except Exception:
            logger.exception("Unable to send privacy request email %s", message.subject)


def send_lead_emails(lead_id):
    """Send the owner notification and visitor confirmation for a saved lead.

    Each email is attempted independently on one SMTP connection and its result
    is recorded on the lead, so a failure is visible in Admin.
    """
    from .models import Lead

    recipient = contact_email()
    if not recipient:
        logger.warning("PUBLIC_CONTACT_EMAIL is not set; lead %s not emailed", lead_id)
        return False

    lead = (
        Lead.objects.select_related("project")
        .prefetch_related("selected_services", "selected_addons")
        .filter(pk=lead_id)
        .first()
    )
    if lead is None:
        return False

    connection = get_connection(fail_silently=False)
    outcomes = {}
    messages = [("owner_notified", _owner_message(lead, recipient))]
    if lead.email:
        messages.append(("confirmation_sent", _confirmation_message(lead, recipient)))

    for flag, message in messages:
        message.connection = connection
        try:
            message.send(fail_silently=False)
            outcomes[flag] = True
        except Exception:
            logger.exception("Unable to send %s email for lead %s", flag, lead.pk)

    if outcomes:
        Lead.objects.filter(pk=lead.pk).update(**outcomes)
    return outcomes.get("owner_notified", False)


def queue_lead_emails(lead):
    """Email the lead. Call after the lead is committed.

    In production this runs on a background thread so the visitor never waits on
    SMTP; the outcome is stored on the lead (owner_notified/confirmation_sent).
    """
    run_in_background(send_lead_emails, lead.pk)
