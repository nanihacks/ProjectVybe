from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from leads.models import ConsentRecord

from .models import CourseWaitlistEntry


DEFAULT_RETENTION_MONTHS = 24


def anonymise_entries(queryset):
    """Remove personal details from waitlist sign-ups. Cannot be undone. Returns how many changed."""
    now = timezone.now()
    changed = 0
    for entry in queryset.filter(anonymised_at__isnull=True):
        with transaction.atomic():
            CourseWaitlistEntry.objects.filter(pk=entry.pk).update(
                name="Anonymised",
                email=f"anonymised-{entry.pk}@example.invalid",
                phone="",
                anonymised_at=now,
            )
            ConsentRecord.objects.filter(waitlist_entry=entry, withdrawn_at__isnull=True).update(withdrawn_at=now)
        changed += 1
    return changed


def entries_past_retention(months=DEFAULT_RETENTION_MONTHS, now=None):
    now = now or timezone.now()
    cutoff = now - timedelta(days=round(months * 30.4375))
    return CourseWaitlistEntry.objects.filter(created_at__lt=cutoff, anonymised_at__isnull=True)
