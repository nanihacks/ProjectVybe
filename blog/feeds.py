from django.conf import settings
from django.contrib.syndication.views import Feed
from django.urls import reverse

from core.seo import absolute_url

from .models import Post


class LatestPostsFeed(Feed):
    """RSS feed of the newest posts. Links use SITE_URL, never the request's Host header."""

    def title(self):
        return f"{settings.SITE_NAME} blog"

    def description(self):
        return "Practical writing on projects, learning and building software."

    def link(self):
        return absolute_url(reverse("blog:list"))

    def feed_url(self):
        return absolute_url(reverse("blog:feed"))

    def items(self):
        return Post.objects.live().select_related("author").order_by("-publish_at")[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt

    def item_link(self, item):
        return absolute_url(item.get_absolute_url())

    def item_pubdate(self, item):
        return item.publish_at

    def item_updateddate(self, item):
        return item.updated_at

    def item_author_name(self, item):
        return item.author.name
