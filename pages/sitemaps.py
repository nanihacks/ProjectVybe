from urllib.parse import urlsplit

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import BlogCategory, Post
from catalog.models import Project, Service
from courses.models import Course
from core.seo import site_origin, site_scheme
from legal.services import published_pages


class ConfiguredOriginSitemap(Sitemap):
    """Keep sitemap locations on SITE_URL instead of the request Host header."""

    def get_urls(self, page=1, site=None, protocol=None):
        origin = urlsplit(site_origin())
        domain = origin.netloc
        return self._urls(page, site_scheme(), domain)


class StaticViewSitemap(ConfiguredOriginSitemap):
    def items(self):
        return (
            "pages:home",
            "pages:project_catalogue",
            "pages:services",
            "pages:about",
            "courses:list",
            "blog:list",
        )

    def location(self, item):
        return reverse(item)


class ProjectSitemap(ConfiguredOriginSitemap):
    def items(self):
        return (
            Project.objects.filter(
                is_published=True,
                category__is_active=True,
            )
            .only("slug", "updated_at")
            .order_by("pk")
        )

    def location(self, item):
        return reverse("pages:project_detail", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at


class ServiceSitemap(ConfiguredOriginSitemap):
    def items(self):
        return Service.objects.filter(is_active=True).only("slug").order_by("pk")

    def location(self, item):
        return reverse("pages:service_detail", kwargs={"slug": item.slug})


class CourseSitemap(ConfiguredOriginSitemap):
    def items(self):
        return Course.objects.filter(is_published=True).only("slug", "updated_at").order_by("pk")

    def location(self, item):
        return reverse("courses:detail", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at


class BlogPostSitemap(ConfiguredOriginSitemap):
    def items(self):
        return Post.objects.live().only("slug", "updated_at").order_by("pk")

    def location(self, item):
        return reverse("blog:detail", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at


class BlogCategorySitemap(ConfiguredOriginSitemap):
    def items(self):
        return BlogCategory.objects.filter(posts__in=Post.objects.live()).distinct().order_by("pk")

    def location(self, item):
        return item.get_absolute_url()


class LegalPageSitemap(ConfiguredOriginSitemap):
    def items(self):
        return list(published_pages().prefetch_related("versions").order_by("footer_order", "title"))

    def location(self, item):
        return item.get_absolute_url()

    def lastmod(self, item):
        # Prefetched, so no extra query per page; versions are ordered newest first.
        versions = list(item.versions.all())
        return versions[0].published_at if versions else None


sitemaps = {
    "static": StaticViewSitemap(),
    "projects": ProjectSitemap(),
    "services": ServiceSitemap(),
    "courses": CourseSitemap(),
    "blog": BlogPostSitemap(),
    "blog_categories": BlogCategorySitemap(),
    "legal": LegalPageSitemap(),
}
