from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .models import ConsentRecord, Lead, PrivacyRequest
from .privacy import anonymise_leads, build_leads_csv
from .utils import send_lead_emails


class ConsentRecordInline(admin.StackedInline):
    model = ConsentRecord
    extra = 0
    can_delete = False
    max_num = 1
    readonly_fields = (
        "contact_consent",
        "age_confirmed",
        "marketing_opt_in",
        "privacy_policy",
        "privacy_policy_version",
        "consent_text",
        "created_at",
        "withdrawn_at",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.action(description="Export selected enquiries as CSV (copy of data)")
def export_csv(modeladmin, request, queryset):
    response = HttpResponse(build_leads_csv(queryset), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="enquiries-{timezone.localdate().isoformat()}.csv"'
    )
    return response


@admin.action(description="Anonymise selected enquiries (removes personal details)", permissions=["change"])
def anonymise_selected(modeladmin, request, queryset):
    if request.POST.get("confirm") == "yes":
        changed = anonymise_leads(queryset)
        modeladmin.message_user(
            request,
            f"Anonymised {changed} enquiries. Their personal details were removed.",
            messages.SUCCESS,
        )
        return None

    context = {
        **modeladmin.admin_site.each_context(request),
        "title": "Anonymise enquiries",
        "opts": modeladmin.model._meta,
        "queryset": queryset.order_by("pk"),
        "selected_pks": list(queryset.values_list("pk", flat=True)),
        "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        "action_name": "anonymise_selected",
    }
    return TemplateResponse(request, "admin/leads/anonymise_confirmation.html", context)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "name",
        "email",
        "phone",
        "project",
        "status",
        "owner_notified",
        "confirmation_sent",
        "created_at",
    )
    list_editable = ("status",)
    search_fields = ("name", "email", "phone", "project__title")
    list_filter = (
        "status",
        "owner_notified",
        "confirmation_sent",
        "consent__marketing_opt_in",
        "project",
        "created_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = (
        "reference",
        "owner_notified",
        "confirmation_sent",
        "created_at",
        "anonymised_at",
    )
    inlines = [ConsentRecordInline]
    actions = ["resend_emails", "withdraw_consent", export_csv, anonymise_selected]
    fields = (
        "reference",
        "project",
        "name",
        "email",
        "phone",
        "selected_services",
        "selected_addons",
        "message",
        "status",
        "owner_notified",
        "confirmation_sent",
        "created_at",
        "anonymised_at",
    )

    @admin.display(description="Reference", ordering="pk")
    def reference(self, obj):
        return obj.reference

    def get_search_results(self, request, queryset, search_term):
        # Let staff search by reference, e.g. "PV-1042" finds lead 42.
        term = search_term.strip().upper()
        if term.startswith("PV-") and term[3:].isdigit():
            lead_pk = int(term[3:]) - 1000
            return queryset.filter(pk=lead_pk), False
        return super().get_search_results(request, queryset, search_term)

    @admin.action(description="Resend notification and confirmation emails", permissions=["change"])
    def resend_emails(self, request, queryset):
        sent = 0
        for lead in queryset:
            if send_lead_emails(lead.pk):
                sent += 1
        self.message_user(
            request,
            f"Notification email sent for {sent} of {queryset.count()} enquiries.",
            level=messages.SUCCESS if sent else messages.WARNING,
        )

    @admin.action(description="Mark consent as withdrawn", permissions=["change"])
    def withdraw_consent(self, request, queryset):
        updated = ConsentRecord.objects.filter(
            lead__in=queryset, withdrawn_at__isnull=True
        ).update(withdrawn_at=timezone.now())
        self.message_user(request, f"Consent withdrawn for {updated} enquiries.")


@admin.action(description="Mark selected requests as done", permissions=["change"])
def mark_requests_done(modeladmin, request, queryset):
    updated = queryset.filter(status=PrivacyRequest.Status.OPEN).update(
        status=PrivacyRequest.Status.DONE,
        handled_at=timezone.now(),
        handled_by=request.user,
    )
    modeladmin.message_user(request, f"Marked {updated} request(s) as done.")


@admin.register(PrivacyRequest)
class PrivacyRequestAdmin(admin.ModelAdmin):
    list_display = ("request_number", "kind", "email", "status", "created_at", "handled_at")
    list_filter = ("status", "kind", "created_at")
    search_fields = ("email", "reference", "message")
    date_hierarchy = "created_at"
    actions = (mark_requests_done,)
    readonly_fields = (
        "request_number",
        "kind",
        "email",
        "reference",
        "message",
        "created_at",
        "handled_at",
        "handled_by",
        "matching_enquiries",
    )
    fields = (
        "request_number",
        "kind",
        "email",
        "reference",
        "message",
        "created_at",
        "matching_enquiries",
        "status",
        "staff_note",
        "handled_at",
        "handled_by",
    )

    def has_add_permission(self, request):
        # Requests arrive from the public form only.
        return False

    @admin.display(description="Enquiries with this email or reference")
    def matching_enquiries(self, obj):
        if obj.pk is None:
            return "-"
        leads = list(Lead.objects.filter(email__iexact=obj.email))
        if obj.reference.startswith("PV-") and obj.reference[3:].isdigit():
            by_reference = Lead.objects.filter(pk=int(obj.reference[3:]) - 1000).first()
            if by_reference is not None and by_reference not in leads:
                leads.append(by_reference)
        if not leads:
            return "None found. The person may have used a different address."
        listing = format_html_join(
            "",
            "<li><a href=\"{}\">{}</a> - {} ({})</li>",
            (
                (
                    reverse("admin:leads_lead_change", args=[lead.pk]),
                    lead.reference,
                    lead.name,
                    lead.email,
                )
                for lead in leads
            ),
        )
        search_link = reverse("admin:leads_lead_changelist") + "?q=" + obj.email
        return format_html(
            "<ul>{}</ul><p>Verify the person first, then open "
            "<a href=\"{}\">the enquiries list</a> to export or anonymise them.</p>",
            listing,
            search_link,
        )

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data and obj.status != PrivacyRequest.Status.OPEN:
            obj.handled_at = timezone.now()
            obj.handled_by = request.user
        super().save_model(request, obj, form, change)
