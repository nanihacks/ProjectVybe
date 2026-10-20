from decimal import Decimal

from django.db import models
from cloudinary.models import CloudinaryField

from .cloudinary import (
    category_asset_folder,
    project_asset_folder,
    project_gallery_asset_folder,
    service_asset_folder,
)
from .pricing import PricedModel
from .validators import validate_youtube_url


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    dropdown_description = models.CharField(
        max_length=160,
        blank=True,
        help_text="Short text shown in the navbar dropdown. Falls back to Description.",
    )
    image = CloudinaryField(
        "image",
        blank=True,
        null=True,
        asset_folder=category_asset_folder,
    )
    homepage_image = CloudinaryField(
        "homepage image",
        blank=True,
        null=True,
        asset_folder=category_asset_folder,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["is_active", "name"])]

    def __str__(self):
        return self.name


class ProjectAddon(PricedModel):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    benefit = models.CharField(
        max_length=200,
        blank=True,
        help_text="One line on what the customer gets, shown on the card.",
    )
    inclusions = models.TextField(
        blank=True,
        help_text="What is included, one per line. The first three are shown on the card.",
    )
    extra_delivery_hours = models.PositiveSmallIntegerField(
        default=0,
        help_text="Hours added to the delivery promise when this add-on is chosen.",
    )
    is_popular = models.BooleanField(default=False, help_text="Shows a 'Popular' badge.")
    is_active = models.BooleanField(default=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "name"]
        indexes = [models.Index(fields=["is_active", "ordering"])]

    def __str__(self):
        return self.name

    @property
    def inclusion_lines(self):
        return [line.strip() for line in self.inclusions.splitlines() if line.strip()]


class Project(PricedModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    short_description = models.CharField(max_length=300)
    description = models.TextField()
    usage = models.TextField(blank=True)
    features = models.TextField(
        blank=True,
        help_text="Enter one feature per line.",
    )
    technology_stack = models.TextField(
        blank=True,
        help_text="Enter one technology per line.",
    )
    requirements = models.TextField(blank=True)
    thumbnail = CloudinaryField(
        "thumbnail",
        blank=True,
        null=True,
        asset_folder=project_asset_folder,
    )
    youtube_demo_url = models.URLField(blank=True, validators=[validate_youtube_url])
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="projects",
    )
    addons = models.ManyToManyField(
        ProjectAddon,
        blank=True,
        related_name="projects",
    )
    accept_online_payment = models.BooleanField(
        default=False,
        help_text=(
            "Visitors can pay for this project online. Also needs a price, "
            "'payments enabled' in Site Settings and the Razorpay keys."
        ),
    )
    delivery_hours = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text="Delivery promise in hours for this project. Leave blank to use the Site Settings value.",
    )
    featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_published", "featured"]),
            models.Index(fields=["category", "is_published"]),
        ]

    def __str__(self):
        return self.title

    def addon_pricing(self, addon):
        """Price of `addon` on this project as (amount, included_free).

        A price set for this project wins over the add-on's own price. `amount` is
        None when there is no price to show or charge. Prefetch `addon_prices` to
        avoid one query per add-on.
        """
        override = next(
            (row for row in self.addon_prices.all() if row.addon_id == addon.id), None
        )
        if override is not None:
            if override.included_free:
                return Decimal("0"), True
            if override.price_override is not None:
                return override.price_override, False
        return addon.effective_price, False


class ProjectAddonPrice(models.Model):
    """A price for one add-on on one project, replacing the add-on's default price."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="addon_prices")
    addon = models.ForeignKey(ProjectAddon, on_delete=models.CASCADE, related_name="project_prices")
    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Replaces the add-on's own price for this project. Leave empty to use the default.",
    )
    included_free = models.BooleanField(
        default=False,
        help_text="This add-on comes free with this project (shown as 'Included').",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "addon"], name="unique_addon_price_per_project"),
        ]
        verbose_name = "add-on price for this project"
        verbose_name_plural = "add-on prices for this project"

    def __str__(self):
        return f"{self.addon.name} on {self.project.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # A priced add-on must also be one of the project's add-ons.
        self.project.addons.add(self.addon)


class ProjectImage(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = CloudinaryField(
        "image",
        asset_folder=project_gallery_asset_folder,
    )
    alt_text = models.CharField(max_length=200)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "id"]
        indexes = [models.Index(fields=["project", "ordering"])]

    def __str__(self):
        return f"{self.project.title} image {self.pk}"


class Service(PricedModel):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    short_description = models.CharField(max_length=300)
    description = models.TextField()
    image = CloudinaryField(
        "image",
        blank=True,
        null=True,
        asset_folder=service_asset_folder,
    )
    is_active = models.BooleanField(default=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "name"]
        indexes = [models.Index(fields=["is_active", "ordering"])]

    def __str__(self):
        return self.name


class Review(models.Model):
    reviewer_name = models.CharField(max_length=120)
    reviewer_role = models.CharField(
        max_length=160,
        blank=True,
        help_text="Optional role, course, or project context shown below the review.",
    )
    message = models.TextField()
    is_published = models.BooleanField(default=False)
    ordering = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordering", "-created_at"]
        indexes = [models.Index(fields=["is_published", "ordering"])]

    def __str__(self):
        return f"{self.reviewer_name} review"
