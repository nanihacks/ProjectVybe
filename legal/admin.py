from django import forms
from django.contrib import admin, messages
from django.utils import timezone

from .models import LegalPage, LegalPageVersion


class LegalPageAdminForm(forms.ModelForm):
    publish_now = forms.BooleanField(
        required=False,
        label="Publish this draft as a new version when I save",
        help_text="Visitors keep seeing the last published version until you tick this and save.",
    )
    effective_date = forms.DateField(
        required=False,
        label="Effective date",
        help_text="Shown to visitors as 'Last updated'. Leave blank for today.",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    change_note = forms.CharField(
        required=False,
        max_length=300,
        label="What changed",
        help_text="For your own records. Not shown to visitors.",
    )

    class Meta:
        model = LegalPage
        fields = "__all__"


class LegalPageVersionInline(admin.TabularInline):
    """Read-only history: published versions can never be edited or removed."""

    model = LegalPageVersion
    extra = 0
    can_delete = False
    fields = ("number", "effective_date", "published_at", "published_by", "change_note")
    readonly_fields = fields
    ordering = ("-number",)
    verbose_name_plural = "Published versions"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.action(description="Publish drafts as new versions (effective today)", permissions=["change"])
def publish_drafts(modeladmin, request, queryset):
    published = 0
    for page in queryset:
        if page.publish(user=request.user, change_note="Published from the list"):
            published += 1
    modeladmin.message_user(
        request,
        f"Published {published} new version(s); {queryset.count() - published} had no changes.",
        messages.SUCCESS if published else messages.INFO,
    )


@admin.register(LegalPage)
class LegalPageAdmin(admin.ModelAdmin):
    form = LegalPageAdminForm
    inlines = (LegalPageVersionInline,)
    actions = (publish_drafts,)
    list_display = (
        "title",
        "slug",
        "is_published",
        "show_in_footer",
        "current_version",
        "draft_is_live",
        "updated_at",
    )
    list_filter = ("is_published", "show_in_footer")
    search_fields = ("title", "slug", "body_markdown")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("current_version", "draft_is_live")
    view_on_site = False
    fieldsets = (
        ("Page", {"fields": ("title", "slug", "hero_copy", "seo_description", "is_published")}),
        ("Draft text", {"fields": ("body_markdown",)}),
        ("Footer link", {"fields": ("show_in_footer", "footer_label", "footer_order")}),
        (
            "Publish",
            {
                "fields": (
                    "current_version",
                    "draft_is_live",
                    "publish_now",
                    "effective_date",
                    "change_note",
                ),
                "description": (
                    "Saving only stores the draft. Tick the box below to make the draft "
                    "the live page as a new version."
                ),
            },
        ),
    )

    @admin.display(description="Live version")
    def current_version(self, obj):
        version = obj.latest_version if obj.pk else None
        return version.label if version else "Not published yet"

    @admin.display(description="Draft is live", boolean=True)
    def draft_is_live(self, obj):
        """Green tick: the draft matches what visitors see. Red cross: unpublished edits."""
        return not obj.has_unpublished_changes() if obj.pk else False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not form.cleaned_data.get("publish_now"):
            if obj.is_published and obj.latest_version is None:
                self.message_user(
                    request,
                    "This page is switched on but has no published version, so visitors "
                    "still see a 404. Tick 'Publish this draft' and save.",
                    messages.WARNING,
                )
            return

        version = obj.publish(
            user=request.user,
            effective_date=form.cleaned_data.get("effective_date") or timezone.localdate(),
            change_note=form.cleaned_data.get("change_note", ""),
        )
        if version is None:
            self.message_user(
                request, "Nothing to publish: the draft matches the live version.", messages.INFO
            )
        else:
            self.message_user(request, f"Published {version}.", messages.SUCCESS)
