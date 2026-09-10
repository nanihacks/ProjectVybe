from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "project", "status", "created_at")
    list_editable = ("status",)
    search_fields = ("name", "email", "phone", "project__title")
    list_filter = ("status", "project", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    fields = (
        "project",
        "name",
        "email",
        "phone",
        "selected_services",
        "selected_addons",
        "message",
        "status",
        "created_at",
    )
