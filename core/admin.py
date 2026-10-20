from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import Faq, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(SingletonModelAdmin):
    fieldsets = (
        (
            "Contact",
            {
                "fields": (
                    "contact_email",
                    "whatsapp_number",
                    "phone",
                    "address",
                    "business_hours",
                    "reply_time_promise",
                ),
                "description": (
                    "Changes appear on the website within about a minute. "
                    "Blank email and WhatsApp fields use the value configured on the server."
                ),
            },
        ),
        (
            "Business details",
            {
                "fields": (
                    "legal_name",
                    "registered_address",
                    "gstin",
                    "grievance_officer_name",
                    "grievance_officer_email",
                ),
                "description": "Used in the footer and in the policy pages.",
            },
        ),
        (
            "Brand and social links",
            {
                "fields": (
                    "footer_tagline",
                    "footer_description",
                    "share_image",
                    ("instagram_url", "show_instagram"),
                    ("linkedin_url", "show_linkedin"),
                    ("youtube_url", "show_youtube"),
                    ("github_url", "show_github"),
                    ("facebook_url", "show_facebook"),
                    ("x_url", "show_x"),
                    "show_whatsapp",
                ),
                "description": "Tick the box beside a link to show its icon in the footer. A link left empty is never shown.",
            },
        ),
        (
            "Announcement bar",
            {
                "fields": (
                    "announcement_enabled",
                    "announcement_text",
                    "announcement_link_url",
                    "announcement_link_label",
                    "announcement_ends_at",
                ),
            },
        ),
        (
            "Homepage",
            {
                "fields": (
                    "hero_eyebrow",
                    "hero_heading",
                    "hero_text",
                    "hero_primary_label",
                    "hero_primary_url",
                    "hero_secondary_label",
                    "hero_secondary_url",
                    "hero_note",
                    "show_categories_section",
                    "show_featured_section",
                    "show_services_section",
                    "show_process_section",
                    "show_value_section",
                    "show_reviews_section",
                ),
            },
        ),
        ("Features", {"fields": ("show_whatsapp_button",)}),
        (
            "Payments",
            {
                "fields": ("payments_enabled",),
                "description": (
                    "Online payment also needs the Razorpay keys on the server, a price on the project "
                    "and 'accept online payment' ticked on that project. Switching this off restores the "
                    "WhatsApp flow everywhere."
                ),
            },
        ),
        (
            "Delivery",
            {
                "fields": (
                    "delivery_window_hours",
                    "business_open_time",
                    "business_close_time",
                    "working_days",
                ),
                "description": (
                    "Orders paid inside business hours are promised within the delivery window. "
                    "Orders paid outside hours are promised from opening time on the next working day."
                ),
            },
        ),
        ("404 page", {"fields": ("not_found_heading", "not_found_message")}),
        (
            "Maintenance mode",
            {
                "fields": (
                    "maintenance_enabled",
                    "maintenance_message",
                    "maintenance_return_time",
                ),
            },
        ),
    )


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = (
        "question", "is_published", "show_on_home", "show_on_projects",
        "show_on_services", "show_on_contact", "show_on_courses", "ordering",
    )
    list_editable = ("is_published", "show_on_home", "show_on_projects", "show_on_services", "show_on_contact", "show_on_courses", "ordering")
    list_filter = ("is_published", "show_on_home", "show_on_projects", "show_on_services", "show_on_contact", "show_on_courses")
    search_fields = ("question", "answer")
    fieldsets = (
        ("Question and answer", {"fields": ("question", "answer")}),
        (
            "Where it appears",
            {
                "fields": ("show_on_home", "show_on_projects", "show_on_services", "show_on_contact", "show_on_courses"),
                "description": "Tick every page that should show this question. Changes appear within about five minutes.",
            },
        ),
        ("Order and visibility", {"fields": ("ordering", "is_published")}),
    )
