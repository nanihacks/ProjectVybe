import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Order(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Awaiting payment"
        PAID = "paid", "Paid"
        PROCESSING = "processing", "In progress"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Payment failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        DRIVE = "drive", "Google Drive link"

    PAID_STATUSES = (Status.PAID, Status.PROCESSING, Status.DELIVERED, Status.REFUNDED)

    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    project = models.ForeignKey(
        "catalog.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="orders",
    )
    project_title = models.CharField(max_length=200)

    customer_name = models.CharField(max_length=120)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40)
    delivery_channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CREATED)

    razorpay_order_id = models.CharField(max_length=40, blank=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=40, blank=True, db_index=True)
    payment_method = models.CharField(max_length=30, blank=True)

    receipt_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    terms_version = models.ForeignKey(
        "legal.LegalPageVersion", on_delete=models.PROTECT, blank=True, null=True, related_name="+"
    )
    refund_policy_version = models.ForeignKey(
        "legal.LegalPageVersion", on_delete=models.PROTECT, blank=True, null=True, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    delivery_deadline = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    delivery_link = models.URLField(blank=True, max_length=500)
    delivery_note = models.TextField(blank=True)

    overdue_alert_sent_at = models.DateTimeField(blank=True, null=True)
    customer_emailed = models.BooleanField(default=False)
    owner_notified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["status", "delivery_deadline"]),
        ]

    def __str__(self):
        return f"{self.reference} - {self.customer_name}"

    @property
    def reference(self):
        if self.pk is None:
            return ""
        return f"PVO-{self.pk + 1000}"

    @property
    def is_paid(self):
        return self.status in self.PAID_STATUSES

    @property
    def is_overdue(self):
        return (
            self.status in (self.Status.PAID, self.Status.PROCESSING)
            and self.delivery_deadline is not None
            and self.delivery_deadline < timezone.now()
        )

    @property
    def refunded_amount(self):
        total = self.refunds.exclude(status=Refund.Status.FAILED).aggregate(s=models.Sum("amount"))["s"]
        return total or Decimal("0")


class OrderItem(models.Model):
    """A line on an order. Copies the name and price so later price edits never change old orders."""

    class Kind(models.TextChoices):
        PROJECT = "project", "Project"
        ADDON = "addon", "Add-on"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    addon = models.ForeignKey(
        "catalog.ProjectAddon", on_delete=models.SET_NULL, blank=True, null=True, related_name="+"
    )
    name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    extra_delivery_hours = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} x{self.quantity}"


class PaymentEvent(models.Model):
    """A webhook delivery from Razorpay. The unique id makes repeats harmless."""

    event_id = models.CharField(max_length=80, unique=True)
    event_type = models.CharField(max_length=60)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, blank=True, null=True, related_name="events")
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_type} {self.event_id}"


class RefundRequest(models.Model):
    """A customer asking for a refund. A person reviews it; nothing is refunded automatically."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, blank=True, null=True, related_name="refund_requests")
    reference = models.CharField(max_length=20, help_text="The order reference the customer typed.")
    email = models.EmailField(help_text="The address the customer says they used. Check it against the order.")
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(blank=True, null=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="+"
    )
    staff_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.request_number} - {self.reference}"

    @property
    def request_number(self):
        if self.pk is None:
            return ""
        return f"RR-{self.pk + 1000}"


class Refund(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True)
    razorpay_refund_id = models.CharField(max_length=40, blank=True, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund {self.amount} for {self.order.reference}"


class ReceiptCounter(models.Model):
    """Last receipt number issued in a financial year (April to March)."""

    financial_year = models.CharField(max_length=7, unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.financial_year}: {self.last_number}"

    @staticmethod
    def financial_year_for(moment):
        local = timezone.localtime(moment)
        start = local.year if local.month >= 4 else local.year - 1
        return f"{start}-{str(start + 1)[-2:]}"

    @classmethod
    def issue(cls, moment=None):
        """Next receipt number, such as PV/2026-27/0001. Call inside a transaction."""
        moment = moment or timezone.now()
        year = cls.financial_year_for(moment)
        with transaction.atomic():
            cls.objects.get_or_create(financial_year=year)
            counter = cls.objects.select_for_update().get(financial_year=year)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
        return f"PV/{year}/{counter.last_number:04d}"
