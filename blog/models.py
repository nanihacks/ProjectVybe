from cloudinary.models import CloudinaryField
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .rendering import render_post


RESERVED_SLUGS = {"category", "tag", "feed", "page"}


def blog_asset_folder(instance):
    return "projectvybe/blog"


class Author(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    bio = models.CharField(max_length=300, blank=True, help_text="One or two sentences shown under posts.")
    avatar = CloudinaryField("photo", blank=True, null=True, asset_folder=blog_asset_folder)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class BlogCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.CharField(max_length=300, blank=True, help_text="Shown at the top of the category page.")
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "name"]
        verbose_name = "blog category"
        verbose_name_plural = "blog categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("blog:category", kwargs={"slug": self.slug})


class Tag(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("blog:tag", kwargs={"slug": self.slug})


class PostQuerySet(models.QuerySet):
    def live(self):
        """Published posts whose publish time has arrived."""
        return self.filter(status=Post.Status.PUBLISHED, publish_at__lte=timezone.now())


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    excerpt = models.CharField(max_length=300, help_text="Shown in lists and when the post is shared.")
    body_markdown = models.TextField(help_text="Write in Markdown. Use ## for section headings.")
    body_html = models.TextField(editable=False, blank=True)
    toc = models.JSONField(default=list, editable=False, blank=True)
    reading_minutes = models.PositiveSmallIntegerField(default=1, editable=False)

    cover = CloudinaryField("cover image", blank=True, null=True, asset_folder=blog_asset_folder)
    cover_alt = models.CharField(max_length=200, blank=True, help_text="Describe the cover image. Required with a cover.")

    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="posts")
    category = models.ForeignKey(BlogCategory, on_delete=models.PROTECT, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    related_projects = models.ManyToManyField(
        "catalog.Project", blank=True, related_name="blog_posts", help_text="Projects this post is about."
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    publish_at = models.DateTimeField(
        default=timezone.now,
        help_text="The post goes live at this time once its status is Published. Set a future time to schedule it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    seo_title = models.CharField(max_length=70, blank=True, help_text="Optional. Defaults to the title.")
    meta_description = models.CharField(max_length=160, blank=True, help_text="Optional. Defaults to the excerpt.")

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-publish_at"]
        indexes = [models.Index(fields=["status", "publish_at"])]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.slug in RESERVED_SLUGS:
            raise ValidationError({"slug": f"'{self.slug}' is reserved for the blog's own pages. Pick another."})
        if self.cover and not self.cover_alt.strip():
            raise ValidationError({"cover_alt": "Describe the cover image for screen readers."})

    def save(self, *args, **kwargs):
        self.body_html, self.toc, self.reading_minutes = render_post(self.body_markdown)
        super().save(*args, **kwargs)

    @property
    def is_live(self):
        return self.status == self.Status.PUBLISHED and self.publish_at <= timezone.now()

    @property
    def page_title(self):
        return self.seo_title or self.title

    @property
    def page_description(self):
        return self.meta_description or self.excerpt

    def get_absolute_url(self):
        return reverse("blog:detail", kwargs={"slug": self.slug})
