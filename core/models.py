import datetime

from cloudinary.models import CloudinaryField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from solo.models import SingletonModel


def validate_link_target(value):
    """Allow only same-site paths or http(s) URLs, so a link can never be a javascript: URL."""
    value = (value or "").strip()
    if not value:
        return
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return
    if value.lower().startswith(("http://", "https://")) and " " not in value:
        return
    raise ValidationError("Enter a path starting with / (like /projects/) or a full http(s):// address.")


def site_asset_folder(instance):
    return "projectvybe/site"


def parse_working_days(value):
    """'0,1,2' -> {0, 1, 2}. Raises ValueError on anything that is not a weekday number."""
    days = set()
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        day = int(part)
        if not 0 <= day <= 6:
            raise ValueError(part)
        days.add(day)
    if not days:
        raise ValueError("empty")
    return days


def validate_working_days(value):
    try:
        parse_working_days(value)
    except ValueError:
        raise ValidationError("Enter weekday numbers from 0 (Monday) to 6 (Sunday), separated by commas.")


class SiteSettings(SingletonModel):
    """Site-wide details editable in Admin without a deploy (one row only)."""

    # Contact
    contact_email = models.EmailField(
        blank=True,
        help_text="Where enquiries and alerts are sent. Leave blank to use the server setting.",
    )
    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Digits with country code, for example 919876543210. Leave blank to use the server setting.",
    )
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True, help_text="Shown in the footer.")
    business_hours = models.CharField(max_length=120, blank=True)
    reply_time_promise = models.CharField(
        max_length=160,
        blank=True,
        default="We usually reply within one working day.",
        help_text="Shown on the enquiry confirmation page.",
    )

    # Business
    legal_name = models.CharField(max_length=160, blank=True)
    registered_address = models.TextField(blank=True)
    gstin = models.CharField("GSTIN", max_length=15, blank=True, help_text="Leave blank until registered.")
    grievance_officer_name = models.CharField(max_length=120, blank=True)
    grievance_officer_email = models.EmailField(blank=True)

    # Brand
    footer_tagline = models.CharField(max_length=80, default="Build. Learn. Grow.")
    footer_description = models.CharField(
        max_length=240,
        default="A technology-focused space for thoughtful software projects, practical learning, and steady progress.",
    )
    share_image = CloudinaryField(
        "share image",
        blank=True,
        null=True,
        asset_folder=site_asset_folder,
        help_text="Default preview image when a page is shared. Use 1200 x 630 pixels.",
    )
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    x_url = models.URLField("X (Twitter) URL", blank=True)
    show_instagram = models.BooleanField("show Instagram", default=True)
    show_linkedin = models.BooleanField("show LinkedIn", default=True)
    show_youtube = models.BooleanField("show YouTube", default=True)
    show_github = models.BooleanField("show GitHub", default=True)
    show_facebook = models.BooleanField("show Facebook", default=True)
    show_x = models.BooleanField("show X (Twitter)", default=True)
    show_whatsapp = models.BooleanField(
        "show WhatsApp",
        default=True,
        help_text="Uses the WhatsApp number set in the Site settings (or the server settings).",
    )

    # Announcement bar
    announcement_enabled = models.BooleanField(default=False)
    announcement_text = models.CharField(max_length=200, blank=True)
    announcement_link_url = models.CharField(max_length=300, blank=True, validators=[validate_link_target])
    announcement_link_label = models.CharField(max_length=40, blank=True)
    announcement_ends_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="The bar hides itself after this time. Leave blank to show it until switched off.",
    )

    # Homepage
    hero_eyebrow = models.CharField(max_length=60, default="ProjectVybe")
    hero_heading = models.CharField(max_length=80, default="Build. Learn. Grow.")
    hero_text = models.TextField(
        default="Practical technology projects, training, mentorship, and software services to help you turn ideas into working solutions.",
    )
    hero_primary_label = models.CharField(max_length=40, default="Explore projects")
    hero_primary_url = models.CharField(
        max_length=300,
        blank=True,
        validators=[validate_link_target],
        help_text="Leave blank to jump to the projects section.",
    )
    hero_secondary_label = models.CharField(max_length=40, default="Our services")
    hero_secondary_url = models.CharField(
        max_length=300,
        blank=True,
        validators=[validate_link_target],
        help_text="Leave blank to open the services page.",
    )
    hero_note = models.CharField(
        max_length=200,
        blank=True,
        default="AI/ML · Software · Development · Training · Mentorship · Publications",
    )
    show_categories_section = models.BooleanField(default=True)
    show_featured_section = models.BooleanField(default=True)
    show_services_section = models.BooleanField(default=True)
    show_process_section = models.BooleanField("show how-it-works section", default=True)
    show_value_section = models.BooleanField("show why-ProjectVybe section", default=True)
    show_reviews_section = models.BooleanField(default=True)

    # Features
    show_whatsapp_button = models.BooleanField(
        default=True,
        help_text="Show the Open WhatsApp button on the enquiry confirmation page.",
    )

    # Payments
    payments_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Master switch for online payment. While off, every project uses the WhatsApp "
            "enquiry flow. Turn on only after the Razorpay keys are set and tested."
        ),
    )

    # Delivery
    delivery_window_hours = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(240)],
        help_text="Delivery promise in hours, counted inside business hours.",
    )
    business_open_time = models.TimeField(default=datetime.time(10, 0))
    business_close_time = models.TimeField(default=datetime.time(19, 0))
    working_days = models.CharField(
        max_length=20,
        default="0,1,2,3,4,5",
        help_text="Comma-separated weekday numbers, Monday=0 to Sunday=6. Default is Monday to Saturday.",
        validators=[validate_working_days],
    )

    # 404 page
    not_found_heading = models.CharField(max_length=120, default="That page could not be found.")
    not_found_message = models.CharField(
        max_length=240,
        default="It may have moved, or the link may be wrong. Try a search or one of the links below.",
    )

    # Maintenance
    maintenance_enabled = models.BooleanField(
        default=False,
        help_text="Visitors see a maintenance page. Staff and the admin keep working.",
    )
    maintenance_message = models.CharField(
        max_length=240,
        blank=True,
        default="ProjectVybe is being updated. Please check back shortly.",
    )
    maintenance_return_time = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional. Shown to visitors as the expected return time.",
    )

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return "Site settings"

    def clean(self):
        super().clean()
        if self.business_open_time and self.business_close_time:
            if self.business_close_time <= self.business_open_time:
                raise ValidationError({"business_close_time": "Closing time must be after opening time."})

    @property
    def working_day_set(self):
        try:
            return parse_working_days(self.working_days)
        except ValueError:
            return {0, 1, 2, 3, 4, 5}

    @property
    def announcement_is_visible(self):
        if not (self.announcement_enabled and self.announcement_text.strip()):
            return False
        return self.announcement_ends_at is None or self.announcement_ends_at > timezone.now()

    @property
    def social_items(self):
        """[(key, label, url)] for the footer icons; `key` picks the icon."""
        links = [
            ("instagram", "Instagram", self.instagram_url, self.show_instagram),
            ("linkedin", "LinkedIn", self.linkedin_url, self.show_linkedin),
            ("youtube", "YouTube", self.youtube_url, self.show_youtube),
            ("github", "GitHub", self.github_url, self.show_github),
            ("facebook", "Facebook", self.facebook_url, self.show_facebook),
            ("x", "X (Twitter)", self.x_url, self.show_x),
        ]
        return [(key, label, url) for key, label, url, shown in links if url and shown]

    @property
    def social_links(self):
        return [(label, url) for _, label, url in self.social_items]


class Faq(models.Model):
    """A question and answer managed in Admin and shown on the pages ticked below."""

    question = models.CharField(max_length=200)
    answer = models.TextField(help_text="Plain text. A blank line starts a new paragraph.")
    show_on_home = models.BooleanField("home page", default=False)
    show_on_projects = models.BooleanField("project pages", default=True)
    show_on_services = models.BooleanField("services page", default=False)
    show_on_contact = models.BooleanField("contact page", default=False)
    show_on_courses = models.BooleanField("courses pages", default=False)
    ordering = models.PositiveIntegerField(default=0, help_text="Lower numbers come first.")
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordering", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question
