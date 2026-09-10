from django.db import models
from cloudinary.models import CloudinaryField

from .cloudinary import (
    category_asset_folder,
    project_asset_folder,
    project_gallery_asset_folder,
    service_asset_folder,
)
from .validators import validate_youtube_url


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
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


class ProjectAddon(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "name"]
        indexes = [models.Index(fields=["is_active", "ordering"])]

    def __str__(self):
        return self.name


class Project(models.Model):
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


class Service(models.Model):
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
