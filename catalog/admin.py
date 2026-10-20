from django.contrib import admin, messages

from .models import (
    Category,
    Project,
    ProjectAddon,
    ProjectAddonPrice,
    ProjectImage,
    Review,
    Service,
)


PRICING_FIELDS = ("price", "sale_price", "price_prefix", "price_note", "show_price")


class ProjectAddonPriceInline(admin.TabularInline):
    model = ProjectAddonPrice
    extra = 0
    fields = ("addon", "price_override", "included_free")
    verbose_name = "add-on price for this project"
    verbose_name_plural = "Add-on prices for this project (optional)"


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    fields = ("image", "alt_text", "ordering")
    ordering = ("ordering", "id")


@admin.action(description="Publish selected projects", permissions=["change"])
def publish_projects(modeladmin, request, queryset):
    updated = queryset.update(is_published=True)
    modeladmin.message_user(
        request,
        f"{updated} project(s) published.",
        messages.SUCCESS,
    )


@admin.action(description="Unpublish selected projects", permissions=["change"])
def unpublish_projects(modeladmin, request, queryset):
    updated = queryset.update(is_published=False)
    modeladmin.message_user(
        request,
        f"{updated} project(s) unpublished.",
        messages.SUCCESS,
    )


@admin.action(description="Mark selected projects as featured", permissions=["change"])
def feature_projects(modeladmin, request, queryset):
    updated = queryset.update(featured=True)
    modeladmin.message_user(
        request,
        f"{updated} project(s) marked as featured.",
        messages.SUCCESS,
    )


@admin.action(description="Remove featured status from selected projects", permissions=["change"])
def unfeature_projects(modeladmin, request, queryset):
    updated = queryset.update(featured=False)
    modeladmin.message_user(
        request,
        f"{updated} project(s) removed from featured projects.",
        messages.SUCCESS,
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)
    ordering = ("name",)
    fieldsets = (
        (
            "Category",
            {
                "fields": ("name", "slug", "description", "dropdown_description", "is_active"),
                "description": (
                    "Description is shown on the home and about category cards. "
                    "Dropdown description is the shorter text in the navbar dropdown."
                ),
            },
        ),
        (
            "Images",
            {
                "fields": ("image", "homepage_image"),
                "description": (
                    "Use image for the category identity/logo. Use homepage image "
                    "for the wider homepage category card. Upload both through Cloudinary."
                ),
            },
        ),
    )


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "is_published",
        "featured",
        "created_at",
        "updated_at",
    )
    search_fields = ("title", "slug", "short_description")
    list_filter = ("category", "is_published", "featured", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("addons",)
    inlines = (ProjectImageInline, ProjectAddonPriceInline)
    actions = (
        publish_projects,
        unpublish_projects,
        feature_projects,
        unfeature_projects,
    )
    fieldsets = (
        (
            "Basic information",
            {
                "fields": ("title", "slug", "category", "short_description"),
            },
        ),
        (
            "Project content",
            {
                "fields": (
                    "description",
                    "usage",
                    "features",
                    "technology_stack",
                    "requirements",
                ),
            },
        ),
        (
            "Media",
            {
                "fields": ("thumbnail",),
                "description": "Upload the project thumbnail through Cloudinary.",
            },
        ),
        (
            "Demo",
            {
                "fields": ("youtube_demo_url",),
            },
        ),
        (
            "Price and checkout",
            {
                "fields": (*PRICING_FIELDS, "accept_online_payment", "delivery_hours"),
                "description": (
                    "Leave the price empty to show no price; visitors then use the WhatsApp "
                    "enquiry. Online payment also needs 'Payments enabled' in Site Settings."
                ),
            },
        ),
        (
            "Project add-ons",
            {
                "fields": ("addons",),
                "description": "Prices for add-ons on this project can be set in the table further down.",
            },
        ),
        (
            "Publishing",
            {
                "fields": ("featured", "is_published"),
            },
        ),
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "price", "is_active", "ordering")
    search_fields = ("name", "slug", "short_description")
    list_filter = ("is_active",)
    ordering = ("ordering", "name")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("Service", {"fields": ("name", "slug", "short_description", "description", "image")}),
        (
            "Price (display only)",
            {
                "fields": PRICING_FIELDS,
                "description": "Shown as a guide on the service card. Services are still arranged by enquiry.",
            },
        ),
        ("Publishing", {"fields": ("is_active", "ordering")}),
    )


@admin.register(ProjectAddon)
class ProjectAddonAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "price", "extra_delivery_hours", "is_active", "ordering")
    search_fields = ("name", "slug", "description")
    list_filter = ("is_active", "is_popular")
    ordering = ("ordering", "name")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("Add-on", {"fields": ("name", "slug", "description", "benefit", "inclusions")}),
        (
            "Default price",
            {
                "fields": PRICING_FIELDS,
                "description": (
                    "Used on every project unless a project sets its own price in the "
                    "project's 'Add-on prices' table."
                ),
            },
        ),
        ("Delivery and display", {"fields": ("extra_delivery_hours", "is_popular", "is_active", "ordering")}),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("reviewer_name", "reviewer_role", "is_published", "ordering", "created_at")
    search_fields = ("reviewer_name", "reviewer_role", "message")
    list_filter = ("is_published",)
    ordering = ("ordering", "-created_at")
    fieldsets = (
        ("Review", {"fields": ("reviewer_name", "reviewer_role", "message")}),
        ("Publishing", {"fields": ("is_published", "ordering")}),
    )
