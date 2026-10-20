from cloudinary.models import CloudinaryField
from django.db import models


def course_asset_folder(instance):
    return "projectvybe/courses"


class Course(models.Model):
    """A planned or running course. While it is not on sale, visitors can join its waitlist."""

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class Format(models.TextChoices):
        LIVE = "live", "Live online"
        RECORDED = "recorded", "Recorded"
        HYBRID = "hybrid", "Live and recorded"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    summary = models.CharField(max_length=300, help_text="One or two sentences shown in the course list.")
    description = models.TextField(blank=True, help_text="Who it is for and what they will be able to do.")
    outline = models.TextField(
        blank=True,
        help_text="The topics covered, one per line, in teaching order.",
    )
    level = models.CharField(max_length=14, choices=Level.choices, default=Level.BEGINNER)
    format = models.CharField(max_length=10, choices=Format.choices, default=Format.LIVE)
    duration = models.CharField(max_length=80, blank=True, help_text="For example '6 weeks' or '20 hours'.")
    expected_launch = models.CharField(
        max_length=80,
        blank=True,
        help_text="For example 'Early 2027'. Leave blank if there is no date yet.",
    )
    cover = CloudinaryField("cover image", blank=True, null=True, asset_folder=course_asset_folder)
    cover_alt = models.CharField(max_length=200, blank=True, help_text="Describe the cover image for screen readers.")
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="courses",
    )
    waitlist_open = models.BooleanField(default=True, help_text="Show the 'notify me' form on this course.")
    is_published = models.BooleanField(default=False)
    ordering = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "title"]
        indexes = [models.Index(fields=["is_published", "ordering"])]

    def __str__(self):
        return self.title

    @property
    def outline_lines(self):
        return [line.strip() for line in self.outline.splitlines() if line.strip()]


class CourseWaitlistEntry(models.Model):
    """Someone who asked to be told when a course (or any course) opens."""

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="waitlist_entries",
        help_text="Empty means they asked to hear about any new course.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    anonymised_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "waitlist entry"
        verbose_name_plural = "waitlist entries"
        indexes = [models.Index(fields=["course", "created_at"])]

    def __str__(self):
        return f"{self.reference} - {self.name}"

    @property
    def reference(self):
        if self.pk is None:
            return ""
        return f"WL-{self.pk + 1000}"
