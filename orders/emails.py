"""Order emails: branded HTML plus a plain-text fallback. Visitor-facing wording is fixed."""

import logging

from django.conf import settings
from django.urls import reverse

from core.email_render import build_email
from core.mail import run_in_background
from core.site import contact_email
from django.core.mail import get_connection
from leads.utils import whatsapp_enquiry_url

from .delivery import describe_deadline
from .models import Order, Refund


logger = logging.getLogger(__name__)


def _from_email():
    return settings.ORDERS_FROM_EMAIL or settings.DEFAULT_FROM_EMAIL or contact_email()


def _absolute(path):
    return f"{settings.SITE_URL}{path}"


def order_url(order):
    return _absolute(reverse("orders:detail", args=[order.public_token]))


def receipt_url(order):
    return _absolute(reverse("orders:receipt", args=[order.public_token]))


def admin_url(order):
    return _absolute(reverse("admin:orders_order_change", args=[order.pk]))


def _item_rows(order):
    return [(item.name, item.line_total) for item in order.items.all()]


def _send(messages):
    connection = get_connection(fail_silently=False)
    sent = []
    for message in messages:
        message.connection = connection
        try:
            message.send(fail_silently=False)
            sent.append(True)
        except Exception:
            logger.exception("Unable to send order email %s", message.subject)
            sent.append(False)
    return sent


def _load(order_id):
    return Order.objects.select_related("project").prefetch_related("items").filter(pk=order_id).first()


def build_paid_emails(order, owner):
    """(customer_message, owner_message_or_None) for a freshly paid order."""
    deadline = describe_deadline(order.delivery_deadline)
    wa = whatsapp_enquiry_url(
        f"Hello ProjectVybe, my order is {order.reference} (payment {order.razorpay_payment_id})."
    )
    customer = build_email(
        f"Payment received - order {order.reference}, delivery {deadline}",
        {
            "heading": "Payment received. Thank you!",
            "preheader": f"Order {order.reference}: delivery {deadline}.",
            "greeting": f"Hello {order.customer_name},",
            "paragraphs": [
                f"We have received your payment for {order.project_title}.",
            ],
            "items": _item_rows(order),
            "total": order.total,
            "details": [
                ("Order", order.reference),
                ("Receipt number", order.receipt_number),
                ("Payment ID", order.razorpay_payment_id),
                ("Delivery", f"{order.get_delivery_channel_display()}, {deadline}"),
            ],
            "links": [("Open printable receipt", receipt_url(order))]
            + ([("Message us on WhatsApp", wa)] if wa else []),
            "after": ["If you did not make this purchase, reply to this email straight away."],
            "button_url": order_url(order),
            "button_label": "View order & receipt",
        },
        to=[order.customer_email],
        from_email=_from_email(),
        reply_to=[owner] if owner else None,
    )
    owner_message = None
    if owner:
        owner_message = build_email(
            f"New paid order {order.reference} - deliver {deadline}",
            {
                "heading": f"New paid order {order.reference}",
                "preheader": f"Deliver {deadline}.",
                "paragraphs": [f"Deliver {deadline}."],
                "items": _item_rows(order),
                "total": order.total,
                "details": [
                    ("Customer", order.customer_name),
                    ("Email", order.customer_email),
                    ("Phone", order.customer_phone),
                    ("Delivery channel", order.get_delivery_channel_display()),
                    ("Receipt", order.receipt_number),
                    ("Payment ID", order.razorpay_payment_id),
                ],
                "button_url": admin_url(order),
                "button_label": "Open in Admin",
                "footnote": "Sent to you because you receive orders for this website.",
            },
            to=[owner],
            from_email=_from_email(),
            reply_to=[order.customer_email],
        )
    return customer, owner_message


def send_paid_emails(order_id):
    """Receipt to the customer and a 'deliver this' alert to the owner."""
    order = _load(order_id)
    if order is None:
        return
    owner = contact_email()
    customer, owner_message = build_paid_emails(order, owner)
    sent = _send([customer] + ([owner_message] if owner_message else []))
    update = {"customer_emailed": sent[0]}
    if owner_message:
        update["owner_notified"] = sent[1]
    Order.objects.filter(pk=order.pk).update(**update)


def queue_paid_emails(order):
    run_in_background(send_paid_emails, order.pk)


def build_delivered_email(order, owner):
    paragraphs = [f"Your order {order.reference} ({order.project_title}) has been delivered."]
    if order.delivery_note:
        paragraphs.append(f"Note from us: {order.delivery_note}")
    paragraphs += [
        f"Your receipt: {receipt_url(order)}",
        "If anything is missing or does not work, reply to this email and we will help. "
        "If you found the project useful, a short review would mean a lot to us.",
    ]
    return build_email(
        f"Your ProjectVybe order {order.reference} has been delivered",
        {
            "heading": "Your order has been delivered",
            "preheader": f"Order {order.reference} is ready.",
            "greeting": f"Hello {order.customer_name},",
            "paragraphs": paragraphs,
            "button_url": order.delivery_link,
            "button_label": "Open your files",
        },
        to=[order.customer_email],
        from_email=_from_email(),
        reply_to=[owner] if owner else None,
    )


def send_delivered_email(order_id):
    order = _load(order_id)
    if order is None:
        return
    _send([build_delivered_email(order, contact_email())])


def build_overdue_email(order, owner):
    promised = describe_deadline(order.delivery_deadline, now=order.delivery_deadline)
    return build_email(
        f"Overdue: {order.reference}",
        {
            "heading": f"Overdue: {order.reference}",
            "paragraphs": [f"This order was promised {promised} and has not been delivered."],
            "details": [
                ("Customer", order.customer_name),
                ("Email", order.customer_email),
                ("Phone", order.customer_phone),
                ("Delivery channel", order.get_delivery_channel_display()),
            ],
            "button_url": admin_url(order),
            "button_label": "Open in Admin",
            "footnote": "Sent to you because you receive orders for this website.",
        },
        to=[owner],
        from_email=_from_email(),
    )


def send_overdue_alert(order_id):
    order = _load(order_id)
    owner = contact_email()
    if order is None or not owner:
        return False
    return _send([build_overdue_email(order, owner)])[0]


def build_refund_request_emails(refund_request, owner):
    number = refund_request.request_number
    messages = []
    if owner:
        messages.append(
            build_email(
                f"Refund request {number} for {refund_request.reference}",
                {
                    "heading": f"Refund request {number}",
                    "paragraphs": [
                        "A refund request was submitted. Check the email matches the order before acting."
                    ],
                    "details": [
                        ("Request", number),
                        ("Order reference given", refund_request.reference),
                        ("Email given", refund_request.email),
                        ("Matched an order", "yes" if refund_request.order_id else "no, check the details"),
                        ("Reason", refund_request.reason),
                    ],
                    "button_url": _absolute(reverse("admin:orders_refundrequest_change", args=[refund_request.pk])),
                    "button_label": "Open in Admin",
                    "footnote": "Sent to you because you receive refund requests for this website.",
                },
                to=[owner],
                from_email=_from_email(),
                reply_to=[refund_request.email],
            )
        )
    # Fixed text only: the acknowledgement never repeats what was typed.
    messages.append(
        build_email(
            f"We received your refund request ({number})",
            {
                "heading": "We received your refund request",
                "preheader": f"Your request number is {number}.",
                "greeting": "Hello,",
                "paragraphs": [
                    f"We have received your refund request ({number}). We review every request and "
                    "will reply to this address within 5 working days.",
                    "If you did not make this request, you can ignore this email.",
                ],
            },
            to=[refund_request.email],
            from_email=_from_email(),
            reply_to=[owner] if owner else None,
        )
    )
    return messages


def send_refund_request_emails(request_id):
    from .models import RefundRequest

    refund_request = RefundRequest.objects.select_related("order").filter(pk=request_id).first()
    if refund_request is None:
        return
    _send(build_refund_request_emails(refund_request, contact_email()))


def build_refund_processed_email(refund, owner):
    order = refund.order
    return build_email(
        f"Refund processed for order {order.reference}",
        {
            "heading": "Your refund has been processed",
            "preheader": f"We refunded {refund.amount} for order {order.reference}.",
            "greeting": f"Hello {order.customer_name},",
            "paragraphs": [
                f"We have refunded Rs. {refund.amount:,.2f} for order {order.reference}.",
                "It usually reaches your bank account in 5 to 7 working days.",
            ],
            "details": [("Refund ID", refund.razorpay_refund_id)],
        },
        to=[order.customer_email],
        from_email=_from_email(),
        reply_to=[owner] if owner else None,
    )


def send_refund_processed_email(refund_id):
    refund = Refund.objects.select_related("order").filter(pk=refund_id).first()
    if refund is None:
        return
    _send([build_refund_processed_email(refund, contact_email())])
