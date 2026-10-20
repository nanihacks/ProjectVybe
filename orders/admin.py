import csv
import io
from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from catalog.pricing import to_paise
from core.mail import run_in_background
from leads.privacy import _csv_safe

from .emails import send_delivered_email
from .gateway import GatewayError, get_gateway
from .models import Order, OrderItem, PaymentEvent, Refund, RefundRequest


class DeliveryForm(forms.Form):
    delivery_link = forms.URLField(required=False, label="Delivery link", help_text="Download or Google Drive link, if any.")
    delivery_note = forms.CharField(
        required=False,
        label="Note to the customer",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Setup steps or anything they should know. Sent in the delivery email.",
    )


class RefundForm(forms.Form):
    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"), label="Amount (INR)")
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


def _confirm_page(modeladmin, request, queryset, form, title, action_name, intro):
    context = {
        **modeladmin.admin_site.each_context(request),
        "title": title,
        "opts": modeladmin.model._meta,
        "queryset": queryset.order_by("pk"),
        "selected_pks": list(queryset.values_list("pk", flat=True)),
        "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        "action_name": action_name,
        "form": form,
        "intro": intro,
    }
    return TemplateResponse(request, "admin/orders/action_confirmation.html", context)


@admin.action(description="Mark as in progress", permissions=["change"])
def mark_processing(modeladmin, request, queryset):
    updated = queryset.filter(status=Order.Status.PAID).update(status=Order.Status.PROCESSING)
    modeladmin.message_user(request, f"{updated} order(s) marked in progress.")


@admin.action(description="Mark delivered and email the customer", permissions=["change"])
def mark_delivered(modeladmin, request, queryset):
    eligible = queryset.filter(status__in=(Order.Status.PAID, Order.Status.PROCESSING))
    if request.POST.get("confirm") == "yes":
        form = DeliveryForm(request.POST)
        if form.is_valid():
            count = 0
            for order in eligible:
                order.status = Order.Status.DELIVERED
                order.delivered_at = timezone.now()
                order.delivery_link = form.cleaned_data["delivery_link"]
                order.delivery_note = form.cleaned_data["delivery_note"]
                order.save(update_fields=["status", "delivered_at", "delivery_link", "delivery_note"])
                run_in_background(send_delivered_email, order.pk)
                count += 1
            modeladmin.message_user(request, f"{count} order(s) marked delivered and the customer emailed.", messages.SUCCESS)
            return None
    else:
        form = DeliveryForm()
    if not eligible.exists():
        modeladmin.message_user(request, "Only paid or in-progress orders can be delivered.", messages.WARNING)
        return None
    return _confirm_page(
        modeladmin, request, eligible, form, "Mark delivered", "mark_delivered",
        "The customer gets an email with this link and note, and the order is marked delivered.",
    )


@admin.action(description="Issue a refund through Razorpay", permissions=["change"])
def issue_refund(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Select exactly one order to refund.", messages.ERROR)
        return None
    order = queryset.get()
    remaining = order.total - order.refunded_amount
    if not order.is_paid or not order.razorpay_payment_id or remaining <= 0:
        modeladmin.message_user(request, "This order has nothing left to refund.", messages.ERROR)
        return None

    if request.POST.get("confirm") == "yes":
        form = RefundForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            if amount > remaining:
                form.add_error("amount", f"At most {remaining} can still be refunded.")
            else:
                try:
                    remote = get_gateway().refund(order.razorpay_payment_id, to_paise(amount))
                except GatewayError as error:
                    modeladmin.message_user(request, f"Razorpay refused the refund: {error}", messages.ERROR)
                    return None
                Refund.objects.create(
                    order=order,
                    amount=amount,
                    reason=form.cleaned_data["reason"],
                    razorpay_refund_id=remote.get("id", ""),
                    created_by=request.user,
                )
                modeladmin.message_user(
                    request,
                    "Refund requested. It becomes 'processed' when Razorpay confirms it.",
                    messages.SUCCESS,
                )
                return None
    else:
        form = RefundForm(initial={"amount": remaining})
    return _confirm_page(
        modeladmin, request, queryset, form, "Issue refund", "issue_refund",
        f"Up to {remaining} can still be refunded to the customer's original payment method.",
    )


CSV_COLUMNS = [
    "date", "receipt_number", "reference", "customer", "email", "items",
    "amount", "method", "payment_id", "status", "refunded",
]


@admin.action(description="Export selected orders as CSV (for your accountant)")
def export_csv(modeladmin, request, queryset):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for order in queryset.prefetch_related("items", "refunds").order_by("paid_at", "pk"):
        writer.writerow(
            [
                _csv_safe(timezone.localtime(order.paid_at).strftime("%Y-%m-%d %H:%M") if order.paid_at else ""),
                _csv_safe(order.receipt_number or ""),
                order.reference,
                _csv_safe(order.customer_name),
                _csv_safe(order.customer_email),
                _csv_safe("; ".join(f"{item.name} ({item.line_total})" for item in order.items.all())),
                order.total,
                _csv_safe(order.payment_method),
                _csv_safe(order.razorpay_payment_id),
                order.status,
                order.refunded_amount,
            ]
        )
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="orders-{timezone.localdate().isoformat()}.csv"'
    return response


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("kind", "name", "unit_price", "quantity", "line_total")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    can_delete = False
    readonly_fields = ("amount", "reason", "razorpay_refund_id", "status", "created_at", "created_by")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


class PaymentEventInline(admin.TabularInline):
    model = PaymentEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event_type", "event_id", "received_at")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "customer_name", "project_title", "total", "status", "paid_at",
        "deadline_flag", "delivery_channel",
    )
    list_filter = ("status", "delivery_channel", "paid_at")
    search_fields = ("customer_name", "customer_email", "razorpay_payment_id", "razorpay_order_id", "receipt_number")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, RefundInline, PaymentEventInline]
    actions = [mark_processing, mark_delivered, issue_refund, export_csv]
    readonly_fields = (
        "reference", "public_token", "project", "project_title", "customer_name", "customer_email",
        "customer_phone", "delivery_channel", "subtotal", "discount", "total", "currency", "status",
        "razorpay_order_id", "razorpay_payment_id", "payment_method", "receipt_number",
        "terms_version", "refund_policy_version", "created_at", "paid_at", "delivery_deadline",
        "delivered_at", "overdue_alert_sent_at", "customer_emailed", "owner_notified", "receipt_link",
    )
    fields = readonly_fields + ("delivery_link", "delivery_note")

    def get_search_results(self, request, queryset, search_term):
        term = search_term.strip().upper()
        if term.startswith("PVO-") and term[4:].isdigit():
            return queryset.filter(pk=int(term[4:]) - 1000), False
        return super().get_search_results(request, queryset, search_term)

    def changelist_view(self, request, extra_context=None):
        if get_gateway().is_test_mode:
            messages.warning(request, "TEST MODE: Razorpay test keys are in use. No real money is moving.")
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Money records are kept. Only unpaid attempts may be removed.
        if obj is not None and obj.is_paid:
            return False
        return super().has_delete_permission(request, obj)

    @admin.display(description="Deadline", ordering="delivery_deadline")
    def deadline_flag(self, obj):
        if obj.delivery_deadline is None:
            return "-"
        text = timezone.localtime(obj.delivery_deadline).strftime("%d %b %H:%M")
        if obj.is_overdue:
            return format_html('<strong style="color:#b3261e">OVERDUE {}</strong>', text)
        return text

    @admin.display(description="Receipt page")
    def receipt_link(self, obj):
        if not obj.is_paid:
            return "-"
        return format_html('<a href="{}" target="_blank" rel="noopener">Open receipt</a>', reverse("orders:receipt", args=[obj.public_token]))


@admin.action(description="Mark selected requests as approved (then issue the refund on the order)", permissions=["change"])
def approve_requests(modeladmin, request, queryset):
    updated = queryset.filter(status=RefundRequest.Status.OPEN).update(
        status=RefundRequest.Status.APPROVED, handled_at=timezone.now(), handled_by=request.user
    )
    modeladmin.message_user(
        request,
        f"{updated} request(s) approved. No money has moved: open the order and use 'Issue a refund'.",
    )


@admin.action(description="Mark selected requests as rejected", permissions=["change"])
def reject_requests(modeladmin, request, queryset):
    updated = queryset.filter(status=RefundRequest.Status.OPEN).update(
        status=RefundRequest.Status.REJECTED, handled_at=timezone.now(), handled_by=request.user
    )
    modeladmin.message_user(request, f"{updated} request(s) rejected. Reply to the customer by email.")


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ("request_number", "reference", "email", "status", "created_at", "order_link")
    list_filter = ("status", "created_at")
    search_fields = ("email", "reference", "reason")
    date_hierarchy = "created_at"
    actions = (approve_requests, reject_requests)
    readonly_fields = (
        "request_number", "reference", "email", "reason", "created_at", "order_link", "handled_at", "handled_by",
    )
    fields = readonly_fields + ("status", "staff_note")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Order")
    def order_link(self, obj):
        if obj.order_id is None:
            return "No matching order. Check the reference and email."
        return format_html('<a href="{}">{}</a>', reverse("admin:orders_order_change", args=[obj.order_id]), obj.order.reference)

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data and obj.status != RefundRequest.Status.OPEN:
            obj.handled_at = timezone.now()
            obj.handled_by = request.user
        super().save_model(request, obj, form, change)
