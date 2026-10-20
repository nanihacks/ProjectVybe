from django.contrib import admin, messages
from django.utils import timezone

from .models import Author, BlogCategory, Post, Tag


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "ordering")
    list_editable = ("ordering",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.action(description="Publish now", permissions=["change"])
def publish_now(modeladmin, request, queryset):
    updated = 0
    for post in queryset:
        post.status = Post.Status.PUBLISHED
        if post.publish_at > timezone.now():
            post.publish_at = timezone.now()
        post.save()
        updated += 1
    modeladmin.message_user(request, f"{updated} post(s) published.", messages.SUCCESS)


@admin.action(description="Move back to draft", permissions=["change"])
def unpublish(modeladmin, request, queryset):
    updated = queryset.update(status=Post.Status.DRAFT)
    modeladmin.message_user(request, f"{updated} post(s) moved back to draft.")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "status", "publish_at", "is_live", "reading_minutes")
    list_filter = ("status", "category", "tags")
    search_fields = ("title", "excerpt", "body_markdown")
    date_hierarchy = "publish_at"
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags", "related_projects")
    autocomplete_fields = ()
    actions = [publish_now, unpublish]
    readonly_fields = ("reading_minutes", "created_at", "updated_at", "preview_link")
    fieldsets = (
        ("Post", {"fields": ("title", "slug", "excerpt", "body_markdown")}),
        ("Cover image", {"fields": ("cover", "cover_alt")}),
        ("Filing", {"fields": ("author", "category", "tags", "related_projects")}),
        (
            "Publishing",
            {
                "fields": ("status", "publish_at", "preview_link"),
                "description": "A post is public once its status is Published and its publish time has passed.",
            },
        ),
        ("Search engines", {"fields": ("seo_title", "meta_description"), "classes": ("collapse",)}),
        ("Details", {"fields": ("reading_minutes", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(boolean=True, description="Live")
    def is_live(self, obj):
        return obj.is_live

    @admin.display(description="Preview")
    def preview_link(self, obj):
        from django.utils.html import format_html

        if obj.pk is None:
            return "Save the post first."
        return format_html('<a href="{}?preview=1" target="_blank" rel="noopener">Open preview</a>', obj.get_absolute_url())
