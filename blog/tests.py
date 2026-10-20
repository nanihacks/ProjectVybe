import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Project
from core.testing import force_login_verified

from .models import Author, BlogCategory, Post, Tag
from .rendering import render_post


class RenderingTests(SimpleTestCase):
    def test_scripts_handlers_and_javascript_links_are_removed(self):
        html, _, _ = render_post(
            "<script>alert(1)</script>\n\n"
            '<img src="https://example.com/a.png" onerror="alert(1)" alt="ok">\n\n'
            "[click](javascript:alert(1))\n\n"
            '<a href="https://example.com" onclick="x()">fine</a>'
        )
        self.assertNotIn("<script", html)
        self.assertNotIn("onerror", html)
        self.assertNotIn("onclick", html)
        self.assertNotIn("javascript:", html)
        self.assertIn('src="https://example.com/a.png"', html)

    def test_only_https_images_survive_and_all_images_load_lazily(self):
        html, _, _ = render_post("![a](http://insecure.example/a.png)\n\n![b](https://ok.example/b.png)")
        self.assertNotIn("insecure.example", html)
        self.assertIn('loading="lazy"', html)

    def test_code_blocks_keep_only_language_classes(self):
        html, _, _ = render_post("```python\nprint(1)\n```")
        self.assertIn("<pre>", html)
        self.assertIn("language-python", html)
        html, _, _ = render_post('<code class="evil big">x</code>')
        self.assertNotIn("evil", html)

    def test_heading_ids_are_prefixed_and_collected_for_the_toc(self):
        html, toc, _ = render_post("## Getting started\n\ntext\n\n### Sub heading\n\n## Main content")
        self.assertIn('id="s-getting-started"', html)
        self.assertIn('id="s-main-content"', html)  # cannot clash with the page's #main-content
        self.assertEqual([item["title"] for item in toc], ["Getting started", "Main content"])
        self.assertEqual(toc[0]["id"], "s-getting-started")

    def test_hand_written_ids_that_could_clash_are_dropped(self):
        html, _, _ = render_post('<h2 id="main-content">Hi</h2>')
        self.assertNotIn('id="main-content"', html)

    def test_reading_time(self):
        self.assertEqual(render_post("word " * 10)[2], 1)
        self.assertEqual(render_post("word " * 221)[2], 2)
        self.assertEqual(render_post("")[2], 1)


@override_settings(SITE_URL="https://example.com")
class BlogTestCase(TestCase):
    def setUp(self):
        self.author = Author.objects.create(name="Priya Nair", slug="priya-nair", bio="Writes about projects.")
        self.category = BlogCategory.objects.create(name="Guides", slug="guides")
        self.tag = Tag.objects.create(name="Django", slug="django")

    def make_post(self, slug="first-post", **extra):
        defaults = {
            "title": "First post",
            "slug": slug,
            "excerpt": "How to start.",
            "body_markdown": "## One\n\nHello.\n\n## Two\n\nWorld.\n\n## Three\n\nBye.",
            "author": self.author,
            "category": self.category,
            "status": Post.Status.PUBLISHED,
            "publish_at": timezone.now() - datetime.timedelta(hours=1),
        }
        defaults.update(extra)
        return Post.objects.create(**defaults)


class PostModelTests(BlogTestCase):
    def test_save_renders_html_toc_and_reading_time(self):
        post = self.make_post()
        self.assertIn("<h2", post.body_html)
        self.assertEqual(len(post.toc), 3)
        self.assertEqual(post.reading_minutes, 1)

    def test_live_requires_published_and_a_past_publish_time(self):
        live = self.make_post("live")
        draft = self.make_post("draft", status=Post.Status.DRAFT)
        scheduled = self.make_post("later", publish_at=timezone.now() + datetime.timedelta(days=1))
        self.assertEqual(list(Post.objects.live()), [live])
        self.assertTrue(live.is_live)
        self.assertFalse(draft.is_live or scheduled.is_live)

    def test_reserved_slugs_are_refused(self):
        for slug in ("feed", "category", "tag", "page"):
            with self.subTest(slug=slug), self.assertRaises(ValidationError):
                self.make_post(slug).__class__(title="x", slug=slug, excerpt="x", author=self.author, category=self.category).clean()

    def test_cover_needs_alt_text(self):
        post = Post(title="x", slug="x", excerpt="x", author=self.author, category=self.category)
        post.cover = "projectvybe/blog/cover"
        with self.assertRaises(ValidationError):
            post.clean()


class BlogPageTests(BlogTestCase):
    def test_list_shows_only_live_posts_newest_first(self):
        self.make_post("old", title="Older post", publish_at=timezone.now() - datetime.timedelta(days=3))
        self.make_post("new", title="Newer post")
        self.make_post("draft", title="Draft post", status=Post.Status.DRAFT)
        self.make_post("later", title="Scheduled post", publish_at=timezone.now() + datetime.timedelta(days=2))
        response = self.client.get(reverse("blog:list"))
        self.assertContains(response, "Newer post")
        self.assertNotContains(response, "Draft post")
        self.assertNotContains(response, "Scheduled post")
        self.assertLess(response.content.find(b"Newer post"), response.content.find(b"Older post"))

    def test_empty_blog_is_friendly(self):
        self.assertContains(self.client.get(reverse("blog:list")), "Nothing here yet.")

    def test_pagination(self):
        for index in range(12):
            self.make_post(f"post-{index}", title=f"Post number {index}", publish_at=timezone.now() - datetime.timedelta(hours=index + 1))
        page_one = self.client.get(reverse("blog:list"))
        self.assertContains(page_one, "Older")
        self.assertContains(self.client.get(reverse("blog:list") + "?page=2"), "Page 2 of 2")
        self.assertContains(self.client.get(reverse("blog:list") + "?page=2"), 'rel="canonical" href="https://example.com/blog/?page=2"')

    def test_detail_has_content_toc_json_ld_and_meta(self):
        post = self.make_post()
        post.tags.add(self.tag)
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, "Hello.")
        self.assertContains(response, 'href="#s-one"')
        self.assertContains(response, '"@type": "BlogPosting"')
        self.assertContains(response, '"headline": "First post"')
        self.assertContains(response, '"@type": "BreadcrumbList"')
        self.assertContains(response, 'property="og:type" content="article"')
        self.assertContains(response, 'property="article:published_time"')
        self.assertContains(response, "Priya Nair")
        self.assertContains(response, reverse("blog:tag", args=["django"]))

    def test_draft_and_scheduled_posts_are_404(self):
        self.make_post("draft", status=Post.Status.DRAFT)
        self.make_post("later", publish_at=timezone.now() + datetime.timedelta(days=1))
        self.assertEqual(self.client.get(reverse("blog:detail", args=["draft"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("blog:detail", args=["later"])).status_code, 404)

    def test_staff_can_preview_a_draft_but_visitors_cannot(self):
        post = self.make_post("draft", status=Post.Status.DRAFT)
        url = post.get_absolute_url() + "?preview=1"
        self.assertEqual(self.client.get(url).status_code, 404)
        staff = get_user_model().objects.create_superuser("boss", "boss@example.com", "pw")
        force_login_verified(self.client, staff)
        response = self.client.get(url)
        self.assertContains(response, "This post is not public yet.")
        self.assertContains(response, "noindex, nofollow")

    def test_category_page_and_tag_page(self):
        other = BlogCategory.objects.create(name="News", slug="news")
        post = self.make_post(title="In guides")
        self.make_post("n", title="In news", category=other)
        post.tags.add(self.tag)
        category_page = self.client.get(self.category.get_absolute_url())
        self.assertContains(category_page, "In guides")
        self.assertNotContains(category_page, "In news")
        tag_page = self.client.get(self.tag.get_absolute_url())
        self.assertContains(tag_page, "In guides")
        self.assertContains(tag_page, "noindex, follow")

    def test_related_projects_show_only_public_ones(self):
        area = Category.objects.create(name="AI", slug="ai-blog")
        shown = Project.objects.create(title="Shown Project", slug="shown", short_description="s", description="d", category=area, is_published=True)
        hidden = Project.objects.create(title="Hidden Project", slug="hidden", short_description="s", description="d", category=area, is_published=False)
        post = self.make_post()
        post.related_projects.add(shown, hidden)
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, "Shown Project")
        self.assertNotContains(response, "Hidden Project")

    def test_navigation_footer_and_feed_links(self):
        home = self.client.get(reverse("pages:home"))
        self.assertContains(home, reverse("blog:list"))
        self.assertContains(home, "application/rss+xml")

    def test_query_budgets(self):
        post = self.make_post()
        with self.assertNumQueries(7):
            self.client.get(reverse("blog:list"))
        with self.assertNumQueries(6):
            self.client.get(post.get_absolute_url())


class FeedAndSitemapTests(BlogTestCase):
    def test_feed_lists_live_posts_with_absolute_links(self):
        self.make_post(title="Live post")
        self.make_post("draft", title="Draft post", status=Post.Status.DRAFT)
        response = self.client.get(reverse("blog:feed"))
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Live post", body)
        self.assertNotIn("Draft post", body)
        self.assertIn("https://example.com/blog/first-post/", body)
        self.assertNotIn("testserver", body)

    def test_sitemap_has_only_live_posts_and_used_categories(self):
        self.make_post()
        self.make_post("draft", status=Post.Status.DRAFT)
        BlogCategory.objects.create(name="Unused", slug="unused")
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("https://example.com/blog/first-post/", sitemap)
        self.assertNotIn("/blog/draft/", sitemap)
        self.assertIn("/blog/category/guides/", sitemap)
        self.assertNotIn("/blog/category/unused/", sitemap)
        self.assertIn("https://example.com/blog/", sitemap)


class BlogAdminTests(BlogTestCase):
    def setUp(self):
        super().setUp()
        self.staff = get_user_model().objects.create_superuser("boss", "boss@example.com", "pw")
        force_login_verified(self.client, self.staff)

    def test_publish_now_makes_a_scheduled_draft_live(self):
        post = self.make_post("later", status=Post.Status.DRAFT, publish_at=timezone.now() + datetime.timedelta(days=3))
        self.client.post(
            reverse("admin:blog_post_changelist"),
            {"action": "publish_now", "_selected_action": [post.pk]},
        )
        post.refresh_from_db()
        self.assertTrue(post.is_live)

    def test_post_changelist_and_form_open(self):
        post = self.make_post()
        self.assertContains(self.client.get(reverse("admin:blog_post_changelist")), "First post")
        self.assertContains(self.client.get(reverse("admin:blog_post_change", args=[post.pk])), "Open preview")
