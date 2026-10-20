import hashlib
import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from catalog.models import Project
from catalog.pricing import to_paise
from core.mail import run_in_background
from core.ratelimit import is_rate_limited
from core.site import get_site_settings
from core.turnstile import FAILURE_MESSAGE, request_passes
from leads.models import ConsentRecord
from leads.utils import whatsapp_enquiry_url
from legal.services import current_privacy_version

from . import services
from .delivery import describe_deadline
from .emails import send_refund_processed_email, send_refund_request_emails
from .forms import CheckoutForm, RefundRequestForm
from .gateway import GatewayError, get_gateway
from .models import Order, PaymentEvent, Refund, RefundRequest


logger = logging.getLogger(__name__)

GATEWAY_DOWN_MESSAGE = "We could not reach the payment service. Nothing was charged. Please try again in a minute."


def _checkout_project(slug):
    """The project, only if online payment is fully available for it right now."""
    project = get_object_or_404(
        Project.objects.select_related("category").prefetch_related("addons", "addon_prices"),
        slug=slug,
        is_published=True,
        category__is_active=True,
    )
    if not (services.checkout_available(project, get_site_settings()) and services.policies_ready()):
        raise Http404("Online payment is not available for this project.")
    return project


def _order_by_token(token):
    return get_object_or_404(Order.objects.prefetch_related("items"), public_token=token)


def _render_checkout(request, project, form, status=200):
    addon_rows = services.purchasable_addons(project)
    chosen = set(form["addons"].value() or []) if form.is_bound else set(request.GET.getlist("addons"))
    return render(
        request,
        "orders/checkout.html",
        {
            "project": project,
            "form": form,
            "consent_fields": [
                form[name]
                for name in ("consent_terms", "consent_contact", "consent_age", "consent_marketing")
            ],
            "addon_rows": [
                {"addon": addon, "amount": amount, "included": included, "checked": str(addon.pk) in chosen}
                for addon, amount, included in addon_rows
            ],
            "project_amount": project.effective_price,
            "breadcrumbs": [
                {"label": "Projects", "url": reverse("pages:project_catalogue")},
                {"label": project.title, "url": reverse("pages:project_detail", args=[project.slug])},
                {"label": "Checkout"},
            ],
        },
        status=status,
    )


@never_cache
def checkout(request, slug):
    project = _checkout_project(slug)
    if request.method != "POST":
        return _render_checkout(request, project, CheckoutForm())

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        return _render_checkout(request, project, form)
    if not request_passes(request):
        form.add_error(None, FAILURE_MESSAGE)
        return _render_checkout(request, project, form)
    if is_rate_limited(request, "checkout", settings.ENQUIRY_RATE_LIMIT, settings.ENQUIRY_RATE_WINDOW):
        form.add_error(None, "Too many attempts from your network. Please wait a few minutes and try again.")
        return _render_checkout(request, project, form, status=429)

    try:
        cart = services.build_cart(project, form.cleaned_data["addons"])
    except services.CartError as error:
        form.add_error(None, str(error))
        return _render_checkout(request, project, form)

    privacy_version = current_privacy_version()
    with transaction.atomic():
        order = services.create_order(
            project,
            cart,
            form.cleaned_data["name"],
            form.cleaned_data["email"],
            form.cleaned_data["phone"],
            form.cleaned_data["delivery_channel"],
        )
        ConsentRecord.objects.create(
            order=order,
            contact_consent=form.cleaned_data["consent_contact"],
            age_confirmed=form.cleaned_data["consent_age"],
            marketing_opt_in=form.cleaned_data["consent_marketing"],
            privacy_policy=privacy_version,
            privacy_policy_version=privacy_version.label if privacy_version else "",
            consent_text=form.consent_text(),
        )
    try:
        services.attach_gateway_order(order)
    except GatewayError:
        order.status = Order.Status.FAILED
        order.save(update_fields=["status"])
        form.add_error(None, GATEWAY_DOWN_MESSAGE)
        return _render_checkout(request, project, form, status=503)
    return redirect("orders:pay", token=order.public_token)


@never_cache
def pay(request, token):
    order = _order_by_token(token)
    if order.is_paid:
        return redirect("orders:detail", token=order.public_token)
    if order.status == Order.Status.CANCELLED or not order.razorpay_order_id:
        raise Http404("This order cannot be paid.")
    gateway = get_gateway()
    return render(
        request,
        "orders/pay.html",
        {
            "order": order,
            "key_id": gateway.key_id,
            "amount_paise": to_paise(order.total),
            "test_mode": gateway.is_test_mode,
            "verify_url": reverse("orders:verify"),
            "failed_url": reverse("orders:failed", args=[order.public_token]),
            "success_url": reverse("orders:detail", args=[order.public_token]),
        },
    )


@require_POST
def verify(request):
    """Called by the browser after Razorpay reports success. Never trusts the browser on its own."""
    razorpay_order_id = request.POST.get("razorpay_order_id", "")
    payment_id = request.POST.get("razorpay_payment_id", "")
    signature = request.POST.get("razorpay_signature", "")
    order = Order.objects.filter(razorpay_order_id=razorpay_order_id).first() if razorpay_order_id else None
    if order is None:
        return JsonResponse({"ok": False}, status=400)

    ok, detail = services.confirm_with_gateway(order, payment_id, signature)
    if not ok:
        logger.warning("Payment confirmation for %s refused: %s", order.reference, detail)
        # The webhook can still mark the order paid if the money really arrived.
        return JsonResponse(
            {"ok": False, "redirect": reverse("orders:failed", args=[order.public_token])}, status=400
        )
    services.mark_paid(order.pk, payment_id, detail)
    return JsonResponse({"ok": True, "redirect": reverse("orders:detail", args=[order.public_token])})


@never_cache
def detail(request, token):
    order = _order_by_token(token)
    if not order.is_paid:
        if order.status in (Order.Status.CREATED, Order.Status.FAILED) and order.razorpay_order_id:
            return redirect("orders:failed", token=order.public_token)
        raise Http404("No paid order here.")
    return render(
        request,
        "orders/detail.html",
        {
            "order": order,
            "deadline_text": describe_deadline(order.delivery_deadline, now=order.paid_at),
            "whatsapp_url": whatsapp_enquiry_url(
                f"Hello ProjectVybe, my order is {order.reference} (payment {order.razorpay_payment_id})."
            ),
            "breadcrumbs": [{"label": "Your order"}],
        },
    )


@never_cache
def failed(request, token):
    order = _order_by_token(token)
    if order.is_paid:
        return redirect("orders:detail", token=order.public_token)
    return render(
        request,
        "orders/failed.html",
        {
            "order": order,
            "can_retry": order.status in (Order.Status.CREATED, Order.Status.FAILED) and order.project_id,
            "breadcrumbs": [{"label": "Payment not completed"}],
        },
    )


@require_POST
def retry(request, token):
    """Start a fresh Razorpay payment for an unpaid order."""
    order = _order_by_token(token)
    if order.is_paid:
        return redirect("orders:detail", token=order.public_token)
    if order.status not in (Order.Status.CREATED, Order.Status.FAILED):
        raise Http404("This order cannot be retried.")
    if is_rate_limited(request, "checkout", settings.ENQUIRY_RATE_LIMIT, settings.ENQUIRY_RATE_WINDOW):
        return HttpResponse("Too many attempts. Please wait a few minutes.", status=429)
    try:
        services.attach_gateway_order(order)
    except GatewayError:
        return render(request, "orders/failed.html", {"order": order, "can_retry": True, "gateway_down": True}, status=503)
    Order.objects.filter(pk=order.pk).update(status=Order.Status.CREATED)
    return redirect("orders:pay", token=order.public_token)


@never_cache
def receipt(request, token):
    order = _order_by_token(token)
    if not order.is_paid:
        raise Http404("No receipt for an unpaid order.")
    return render(
        request,
        "orders/receipt.html",
        {"order": order, "business": get_site_settings(request), "has_gstin": bool(get_site_settings(request).gstin)},
    )


def refund_request(request):
    if request.method == "POST":
        form = RefundRequestForm(request.POST)
        if form.is_valid():
            if not request_passes(request):
                form.add_error(None, FAILURE_MESSAGE)
            elif is_rate_limited(request, "refund", settings.ENQUIRY_RATE_LIMIT, settings.ENQUIRY_RATE_WINDOW):
                form.add_error(None, "Too many requests from your network. Please wait a few minutes and try again.")
                return render(
                    request,
                    "orders/refund_request.html",
                    {"form": form, "breadcrumbs": [{"label": "Refund request"}]},
                    status=429,
                )
            else:
                instance = form.save(commit=False)
                number = int(instance.reference.split("-")[1]) - 1000
                instance.order = Order.objects.filter(
                    pk=number, customer_email__iexact=instance.email
                ).first()
                instance.save()
                run_in_background(send_refund_request_emails, instance.pk)
                request.session["refund_request"] = {"id": instance.pk}
                return redirect("orders:refund_request_received")
    else:
        form = RefundRequestForm(initial={"reference": request.GET.get("order", "")})
    return render(
        request,
        "orders/refund_request.html",
        {"form": form, "breadcrumbs": [{"label": "Refund request"}]},
    )


def refund_request_received(request):
    stored = request.session.get("refund_request")
    instance = RefundRequest.objects.filter(pk=stored.get("id")).first() if stored else None
    if instance is None:
        return redirect("orders:refund_request")
    return render(
        request,
        "orders/refund_request_received.html",
        {"request_number": instance.request_number, "breadcrumbs": [{"label": "Refund request received"}]},
    )


@csrf_exempt
@require_POST
def webhook(request):
    """Razorpay server-to-server events. Signature is required; repeats are ignored."""
    gateway = get_gateway()
    raw_body = request.body
    if not gateway.verify_webhook_signature(raw_body, request.headers.get("X-Razorpay-Signature", "")):
        return HttpResponse(status=400)
    try:
        payload = json.loads(raw_body)
    except ValueError:
        return HttpResponse(status=400)

    event_type = payload.get("event", "")
    event_id = request.headers.get("X-Razorpay-Event-Id", "") or "body-" + hashlib.sha256(raw_body).hexdigest()
    entities = payload.get("payload", {})
    payment = entities.get("payment", {}).get("entity", {})
    refund_entity = entities.get("refund", {}).get("entity", {})

    try:
        with transaction.atomic():
            order = None
            if payment.get("order_id"):
                order = Order.objects.filter(razorpay_order_id=payment["order_id"]).first()
            PaymentEvent.objects.create(event_id=event_id, event_type=event_type, order=order, payload=payload)
            _handle_event(event_type, order, payment, refund_entity)
    except IntegrityError:
        return HttpResponse(status=200)  # already handled
    return HttpResponse(status=200)


def _handle_event(event_type, order, payment, refund_entity):
    if event_type == "payment.captured" and order is not None:
        amount_ok = int(payment.get("amount", -1)) == to_paise(order.total) and payment.get("currency") == "INR"
        if amount_ok:
            services.mark_paid(order.pk, payment.get("id", ""), payment.get("method", ""))
        else:
            logger.error("Webhook amount mismatch for %s", order.reference)
    elif event_type == "payment.failed" and order is not None:
        services.mark_failed(order.pk)
    elif event_type in ("refund.processed", "refund.failed"):
        refund = Refund.objects.select_related("order").filter(razorpay_refund_id=refund_entity.get("id", "")).first()
        if refund is None:
            return
        if event_type == "refund.failed":
            Refund.objects.filter(pk=refund.pk).update(status=Refund.Status.FAILED)
            return
        if refund.status != Refund.Status.PROCESSED:
            Refund.objects.filter(pk=refund.pk).update(status=Refund.Status.PROCESSED)
            if refund.order.refunded_amount >= refund.order.total:
                Order.objects.filter(pk=refund.order_id).update(status=Order.Status.REFUNDED)
            run_in_background(send_refund_processed_email, refund.pk)
