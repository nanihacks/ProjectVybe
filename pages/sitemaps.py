from urllib.parse import urlsplit

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Project
from core.seo import site_origin, site_scheme


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
            "pages:privacy_policy",
            "pages:terms",
            "pages:refund_policy",
            "pages:cookies",
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


sitemaps = {
    "static": StaticViewSitemap(),
    "projects": ProjectSitemap(),
}
