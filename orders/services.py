"""Checkout rules: what can be bought, what it costs, and what happens when money arrives."""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from catalog.pricing import to_paise
from core.site import get_site_settings
from legal.services import get_public_page

from .delivery import delivery_deadline
from .gateway import GatewayError, get_gateway
from .models import Order, OrderItem, ReceiptCounter


logger = logging.getLogger(__name__)

TERMS_SLUG = "terms-and-conditions"
REFUND_SLUG = "refund-policy"


class CartError(Exception):
    """The chosen items cannot be bought online."""


def checkout_available(project, site_settings=None, gateway=None):
    """Online payment is offered only when every one of these holds."""
    site_settings = site_settings or get_site_settings()
    gateway = gateway or get_gateway()
    return bool(
        site_settings.payments_enabled
        and project.accept_online_payment
        and project.is_purchasable
        and gateway.is_configured
    )


def policies_ready():
    """Terms and Refund Policy must both be published before anyone can pay."""
    return get_public_page(TERMS_SLUG)[1] is not None and get_public_page(REFUND_SLUG)[1] is not None


def purchasable_addons(project):
    """[(addon, amount, included_free)] the customer may pick online, in display order."""
    rows = []
    for addon in project.addons.all():
        if not addon.is_active:
            continue
        amount, included = project.addon_pricing(addon)
        if amount is None:
            continue
        rows.append((addon, amount, included))
    return sorted(rows, key=lambda row: (row[0].ordering, row[0].name))


@dataclass
class Cart:
    lines: list = field(default_factory=list)  # (kind, addon, name, amount, extra_hours)
    total: Decimal = Decimal("0")
    extra_hours: int = 0


def build_cart(project, addon_ids):
    """Price the project and chosen add-ons from the database. Browser-sent prices are never used."""
    if not project.is_purchasable:
        raise CartError("This project has no online price.")
    available = {addon.pk: (addon, amount) for addon, amount, _ in purchasable_addons(project)}
    chosen = []
    for raw in addon_ids:
        try:
            addon_id = int(raw)
        except (TypeError, ValueError):
            raise CartError("Unknown add-on.")
        if addon_id not in available:
            raise CartError("One of the chosen add-ons is not available.")
        if addon_id not in chosen:
            chosen.append(addon_id)

    cart = Cart()
    cart.lines.append(("project", None, project.title, project.effective_price, 0))
    cart.total = project.effective_price
    for addon_id in chosen:
        addon, amount = available[addon_id]
        cart.lines.append(("addon", addon, addon.name, amount, addon.extra_delivery_hours))
        cart.total += amount
        cart.extra_hours = max(cart.extra_hours, addon.extra_delivery_hours)
    return cart


def create_order(project, cart, customer_name, customer_email, customer_phone, channel):
    terms = get_public_page(TERMS_SLUG)[1]
    refund = get_public_page(REFUND_SLUG)[1]
    with transaction.atomic():
        order = Order.objects.create(
            project=project,
            project_title=project.title,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            delivery_channel=channel,
            subtotal=cart.total,
            total=cart.total,
            terms_version=terms,
            refund_policy_version=refund,
        )
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                kind=kind,
                addon=addon,
                name=name,
                unit_price=amount,
                line_total=amount,
                extra_delivery_hours=hours,
            )
            for kind, addon, name, amount, hours in cart.lines
        )
    return order


def attach_gateway_order(order, gateway=None):
    """Create the Razorpay order for `order` (again, on a retry). Raises GatewayError."""
    gateway = gateway or get_gateway()
    remote = gateway.create_order(to_paise(order.total), order.reference, {"order": order.reference})
    order.razorpay_order_id = remote["id"]
    order.save(update_fields=["razorpay_order_id"])
    return remote


def delivery_hours_for(order, site_settings=None):
    site_settings = site_settings or get_site_settings()
    base = (order.project.delivery_hours if order.project else None) or site_settings.delivery_window_hours
    extra = max((item.extra_delivery_hours for item in order.items.all()), default=0)
    return base + extra


def mark_paid(order_id, payment_id, method=""):
    """Record a confirmed payment exactly once. Returns (order, newly_paid).

    Safe to call from the browser step and the webhook together: the order row is
    locked, so only the first caller issues the receipt number and sends emails.
    """
    from .emails import queue_paid_emails

    with transaction.atomic():
        order = (
            Order.objects.select_for_update().select_related("project").get(pk=order_id)
        )
        if order.is_paid:
            return order, False
        site_settings = get_site_settings()
        now = timezone.now()
        order.status = Order.Status.PAID
        order.paid_at = now
        order.razorpay_payment_id = payment_id
        order.payment_method = method[:30]
        order.receipt_number = ReceiptCounter.issue(now)
        order.delivery_deadline = delivery_deadline(
            now,
            delivery_hours_for(order, site_settings),
            site_settings.business_open_time,
            site_settings.business_close_time,
            site_settings.working_day_set,
        )
        order.save()
    queue_paid_emails(order)
    return order, True


def mark_failed(order_id):
    """A failed attempt, only while the order is still waiting for payment."""
    return Order.objects.filter(pk=order_id, status=Order.Status.CREATED).update(status=Order.Status.FAILED)


def confirm_with_gateway(order, payment_id, signature, gateway=None):
    """Check the browser callback end to end. Returns (ok, reason)."""
    gateway = gateway or get_gateway()
    if not gateway.verify_payment_signature(order.razorpay_order_id, payment_id, signature):
        return False, "signature"
    try:
        payment = gateway.fetch_payment(payment_id)
    except GatewayError:
        return False, "unreachable"
    if (
        payment.get("order_id") != order.razorpay_order_id
        or payment.get("status") != "captured"
        or payment.get("currency") != "INR"
        or int(payment.get("amount", -1)) != to_paise(order.total)
    ):
        return False, "mismatch"
    return True, payment.get("method", "")
