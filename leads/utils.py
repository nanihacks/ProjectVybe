from re import sub
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMessage


def whatsapp_enquiry_url(message):
    number = sub(r"\D", "", settings.WHATSAPP_NUMBER)
    if not number:
        return ""
    return f"https://wa.me/{number}?{urlencode({'text': message})}"


def send_enquiry_email(cleaned_data):
    recipient = settings.PUBLIC_CONTACT_EMAIL.strip()
    if not recipient:
        return False

    project = cleaned_data.get("project")
    subject = "New ProjectVybe enquiry"
    if project:
        subject = f"New ProjectVybe enquiry: {project.title}"

    notification = EmailMessage(
        subject=subject,
        body=build_enquiry_message(cleaned_data),
        from_email=settings.DEFAULT_FROM_EMAIL or recipient,
        to=[recipient],
        reply_to=[cleaned_data["email"]] if cleaned_data.get("email") else None,
    )
    notification.send(fail_silently=False)

    visitor_email = cleaned_data.get("email", "").strip()
    if visitor_email:
        confirmation = EmailMessage(
            subject="We received your ProjectVybe enquiry",
            body=(
                f"Hello {cleaned_data.get('name', '').strip() or 'there'},\n\n"
                "Thank you for contacting ProjectVybe. We have received your "
                "enquiry and will review it before getting back to you.\n\n"
                "For your reference, we received:\n\n"
                f"{build_enquiry_message(cleaned_data)}\n\n"
                "If you need to add anything, reply to this email.\n\n"
                "ProjectVybe\n"
                f"{recipient}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL or recipient,
            to=[visitor_email],
            reply_to=[recipient],
        )
        confirmation.send(fail_silently=False)

    return True


def build_enquiry_message(cleaned_data):
    lines = ["Hello ProjectVybe,", ""]

    if cleaned_data.get("project"):
        lines.extend(
            [
                f"I am interested in the {cleaned_data['project'].title} project.",
                "",
            ]
        )
    else:
        lines.append("I would like to make an enquiry.")

    if cleaned_data.get("name"):
        lines.append(f"Name: {cleaned_data['name']}")
    if cleaned_data.get("email"):
        lines.append(f"Email: {cleaned_data['email']}")
    if cleaned_data.get("phone"):
        lines.append(f"Phone: {cleaned_data['phone']}")

    services = list(cleaned_data.get("selected_services") or [])
    addons = list(cleaned_data.get("selected_addons") or [])
    additional_services = [item.name for item in [*services, *addons]]
    if additional_services:
        lines.extend(
            [
                "",
                "Additional services:",
                ", ".join(additional_services),
            ]
        )

    if cleaned_data.get("message"):
        lines.extend(["", f"Message: {cleaned_data['message']}"])

    return "\n".join(lines)
