from django.conf import settings
from django.db import models

from catalog.models import Project, ProjectAddon, Service


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CLOSED = "closed", "Closed"

    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="leads",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    selected_services = models.ManyToManyField(
        Service,
        blank=True,
        related_name="leads",
        help_text="Choose company services to discuss.",
    )
    selected_addons = models.ManyToManyField(
        ProjectAddon,
        blank=True,
        related_name="leads",
        help_text="Choose project-specific add-ons to discuss.",
    )
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    owner_notified = models.BooleanField(
        default=False,
        help_text="The notification email to the ProjectVybe inbox was sent.",
    )
    confirmation_sent = models.BooleanField(
        default=False,
        help_text="The confirmation email to the visitor was sent.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    anonymised_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Set when personal details were removed (privacy request or retention).",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["project", "created_at"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.email}"

    @property
    def reference(self):
        if self.pk is None:
            return ""
        return f"PV-{self.pk + 1000}"


class ConsentRecord(models.Model):
    """Evidence of what a visitor agreed to when they submitted an enquiry."""

    lead = models.OneToOneField(
        Lead,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="consent",
    )
    waitlist_entry = models.OneToOneField(
        "courses.CourseWaitlistEntry",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="consent",
    )
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="consent",
    )
    contact_consent = models.BooleanField(default=False)
    age_confirmed = models.BooleanField(default=False)
    marketing_opt_in = models.BooleanField(default=False)
    privacy_policy = models.ForeignKey(
        "legal.LegalPageVersion",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="+",
        help_text="The exact Privacy Policy version the visitor agreed to.",
    )
    privacy_policy_version = models.CharField(
        max_length=40,
        help_text="Label of that version, kept even if the policy is later removed.",
    )
    consent_text = models.TextField(
        help_text="The exact wording shown to the visitor.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        subject = self.lead or self.order or self.waitlist_entry
        return f"Consent for {subject.reference if subject else 'deleted record'}"


class PrivacyRequest(models.Model):
    """A person asking to see, correct, delete or stop using their information."""

    class Kind(models.TextChoices):
        WITHDRAW_CONSENT = "withdraw_consent", "Withdraw my consent"
        STOP_UPDATES = "stop_updates", "Stop sending me updates"
        ACCESS = "access", "Send me a copy of my information"
        CORRECT = "correct", "Correct my information"
        DELETE = "delete", "Delete my information"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"
        REJECTED = "rejected", "Rejected"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    email = models.EmailField(help_text="The address the person says they used. Check it before acting.")
    reference = models.CharField(
        max_length=20,
        blank=True,
        help_text="An enquiry reference such as PV-1042, if they gave one.",
    )
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(blank=True, null=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="+",
    )
    staff_note = models.TextField(blank=True, help_text="What was done, for your records.")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.request_number} - {self.get_kind_display()}"

    @property
    def request_number(self):
        if self.pk is None:
            return ""
        return f"PR-{self.pk + 1000}"
