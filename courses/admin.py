import csv
import io

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.db.models import Count
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone

from leads.models import ConsentRecord
from leads.privacy import _csv_safe

from .models import Course, CourseWaitlistEntry
from .privacy import anonymise_entries


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "format", "expected_launch", "waitlist_count", "is_published", "ordering")
    list_editable = ("is_published", "ordering")
    list_filter = ("is_published", "level", "format")
    search_fields = ("title", "summary")
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        ("Course", {"fields": ("title", "slug", "summary", "description", "outline")}),
        ("Details", {"fields": ("level", "format", "duration", "expected_launch", "category")}),
        ("Cover image", {"fields": ("cover", "cover_alt")}),
        ("Visibility", {"fields": ("is_published", "waitlist_open", "ordering")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_waitlist=Count("waitlist_entries"))

    @admin.display(description="Waitlist", ordering="_waitlist")
    def waitlist_count(self, obj):
        return obj._waitlist


@admin.action(description="Export selected sign-ups as CSV")
def export_csv(modeladmin, request, queryset):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["reference", "course", "name", "email", "phone", "joined", "marketing_opt_in", "privacy_policy_version"])
    for entry in queryset.select_related("course", "consent"):
        consent = getattr(entry, "consent", None)
        writer.writerow(
            [
                entry.reference,
                _csv_safe(entry.course.title if entry.course else "Any new course"),
                _csv_safe(entry.name),
                _csv_safe(entry.email),
                _csv_safe(entry.phone),
                timezone.localtime(entry.created_at).strftime("%Y-%m-%d %H:%M"),
                "yes" if consent and consent.marketing_opt_in else "no",
                consent.privacy_policy_version if consent else "",
            ]
        )
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="waitlist-{timezone.localdate().isoformat()}.csv"'
    return response


@admin.action(description="Anonymise selected sign-ups (removes personal details, cannot be undone)", permissions=["change"])
def anonymise_selected(modeladmin, request, queryset):
    if request.POST.get("confirm") == "yes":
        changed = anonymise_entries(queryset)
        modeladmin.message_user(request, f"Anonymised {changed} sign-ups.", messages.SUCCESS)
        return None
    context = {
        **modeladmin.admin_site.each_context(request),
        "title": "Anonymise sign-ups",
        "opts": modeladmin.model._meta,
        "queryset": queryset.order_by("pk"),
        "selected_pks": list(queryset.values_list("pk", flat=True)),
        "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        "action_name": "anonymise_selected",
    }
    return TemplateResponse(request, "admin/courses/anonymise_confirmation.html", context)


class WaitlistConsentInline(admin.StackedInline):
    model = ConsentRecord
    fk_name = "waitlist_entry"
    extra = 0
    can_delete = False
    max_num = 1
    readonly_fields = (
        "contact_consent", "age_confirmed", "marketing_opt_in", "privacy_policy",
        "privacy_policy_version", "consent_text", "created_at", "withdrawn_at",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CourseWaitlistEntry)
class CourseWaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("reference", "name", "email", "course", "created_at")
    list_filter = ("course", "created_at")
    search_fields = ("name", "email")
    date_hierarchy = "created_at"
    readonly_fields = ("reference", "name", "email", "phone", "course", "created_at", "anonymised_at")
    fields = readonly_fields
    inlines = [WaitlistConsentInline]
    actions = [export_csv, anonymise_selected]

    def has_add_permission(self, request):
        return False
