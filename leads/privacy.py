import csv
import io
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import ConsentRecord, Lead


ANONYMISED_NAME = "Anonymised"
REMOVED_MESSAGE = "[removed]"
DEFAULT_RETENTION_MONTHS = 24

CSV_COLUMNS = [
    "reference",
    "name",
    "email",
    "phone",
    "project",
    "services",
    "add_ons",
    "message",
    "status",
    "received_at",
    "agreed_to_contact",
    "confirmed_18_or_parent",
    "marketing_updates",
    "privacy_policy_version",
    "consent_recorded_at",
    "consent_withdrawn_at",
    "anonymised_at",
]


def anonymise_leads(queryset):
    """Remove personal details from enquiries. Cannot be undone. Returns how many changed."""
    now = timezone.now()
    changed = 0
    for lead in queryset.filter(anonymised_at__isnull=True):
        with transaction.atomic():
            Lead.objects.filter(pk=lead.pk).update(
                name=ANONYMISED_NAME,
                email=f"anonymised-{lead.pk}@example.invalid",
                phone="",
                message=REMOVED_MESSAGE,
                anonymised_at=now,
            )
            lead.selected_services.clear()
            lead.selected_addons.clear()
            # Anonymising ends any permission to contact or send updates.
            ConsentRecord.objects.filter(lead=lead, withdrawn_at__isnull=True).update(
                withdrawn_at=now
            )
        changed += 1
    return changed


def leads_past_retention(months=DEFAULT_RETENTION_MONTHS, now=None):
    """Enquiries older than `months` whose personal details are still stored."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=round(months * 30.4375))
    return Lead.objects.filter(created_at__lt=cutoff, anonymised_at__isnull=True)


def _csv_safe(value):
    """Stop spreadsheet programs treating a text cell as a formula."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def build_leads_csv(queryset):
    """CSV of everything held about the selected enquiries (for an access request)."""
    queryset = queryset.select_related("project", "consent").prefetch_related(
        "selected_services", "selected_addons"
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for lead in queryset:
        consent = getattr(lead, "consent", None)
        writer.writerow(
            [
                _csv_safe(value)
                for value in (
                    lead.reference,
                    lead.name,
                    lead.email,
                    lead.phone,
                    lead.project.title if lead.project else "",
                    "; ".join(item.name for item in lead.selected_services.all()),
                    "; ".join(item.name for item in lead.selected_addons.all()),
                    lead.message,
                    lead.get_status_display(),
                    lead.created_at.isoformat(),
                    "yes" if consent and consent.contact_consent else "no",
                    "yes" if consent and consent.age_confirmed else "no",
                    "yes" if consent and consent.marketing_opt_in else "no",
                    consent.privacy_policy_version if consent else "",
                    consent.created_at.isoformat() if consent else "",
                    consent.withdrawn_at.isoformat() if consent and consent.withdrawn_at else "",
                    lead.anonymised_at.isoformat() if lead.anonymised_at else "",
                )
            ]
        )
    return output.getvalue()
