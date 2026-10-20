from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from .rendering import render_markdown


# Pages that keep their original, memorable URLs. Everything else is served at
# /legal/<slug>/.
PAGE_URL_NAMES = {
    "privacy-policy": "pages:privacy_policy",
    "terms-and-conditions": "pages:terms",
    "refund-policy": "pages:refund_policy",
    "cookie-policy": "pages:cookies",
    "grievance-redressal": "pages:grievance_redressal",
    "shipping-delivery-policy": "pages:shipping_delivery_policy",
    "academic-integrity-policy": "pages:academic_integrity_policy",
}


class LegalPage(models.Model):
    """A policy page. Edit the draft here; publishing snapshots it as a new version."""

    title = models.CharField(max_length=160)
    slug = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Part of the page address. Changing it changes the page URL for new pages.",
    )
    hero_copy = models.CharField(
        max_length=300,
        blank=True,
        help_text="One-sentence summary shown under the title.",
    )
    seo_description = models.CharField(max_length=300, blank=True)
    body_markdown = models.TextField(
        help_text=(
            "The draft. Visitors see it only after you publish a new version. Use ## for "
            "headings, - for lists and **bold**. Placeholders such as {contact_email}, "
            "{legal_name}, {registered_address}, {grievance_officer_name}, "
            "{grievance_officer_email} and {whatsapp_number} are filled from Site Settings."
        ),
    )
    footer_label = models.CharField(
        max_length=80,
        blank=True,
        help_text="Text of the footer link. Leave blank to use the title.",
    )
    show_in_footer = models.BooleanField(default=True)
    footer_order = models.PositiveSmallIntegerField(default=100)
    is_published = models.BooleanField(
        default=False,
        help_text="Unpublished pages show a 404 to visitors, whatever versions exist.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["footer_order", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        name = PAGE_URL_NAMES.get(self.slug)
        if name:
            return reverse(name)
        return reverse("pages:legal_page", kwargs={"slug": self.slug})

    @property
    def footer_text(self):
        return self.footer_label or self.title

    @property
    def latest_version(self):
        return self.versions.order_by("-number").first()

    def has_unpublished_changes(self):
        latest = self.latest_version
        return latest is None or latest.body_markdown != self.body_markdown

    def publish(self, user=None, effective_date=None, change_note=""):
        """Snapshot the draft as the next version. Returns None if nothing changed."""
        with transaction.atomic():
            # Lock the page row so two staff publishing at once get different numbers.
            page = LegalPage.objects.select_for_update().get(pk=self.pk)
            latest = page.versions.order_by("-number").first()
            if latest is not None and latest.body_markdown == page.body_markdown:
                return None
            return LegalPageVersion.objects.create(
                page=page,
                number=(latest.number + 1) if latest else 1,
                effective_date=effective_date or timezone.localdate(),
                change_note=change_note,
                body_markdown=page.body_markdown,
                body_html=render_markdown(page.body_markdown),
                published_by=user if getattr(user, "pk", None) else None,
            )


class LegalPageVersion(models.Model):
    """An immutable published copy of a policy. Consent records point at these."""

    page = models.ForeignKey(LegalPage, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    effective_date = models.DateField()
    change_note = models.CharField(
        max_length=300,
        blank=True,
        help_text="What changed, for your own records.",
    )
    body_markdown = models.TextField()
    body_html = models.TextField(help_text="Sanitised HTML made from the Markdown when published.")
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["page", "number"], name="unique_legal_version_number"),
        ]

    def __str__(self):
        return f"{self.page.title} v{self.number} ({self.effective_date:%d %b %Y})"

    @property
    def label(self):
        return f"v{self.number} ({self.effective_date.isoformat()})"
