from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.backends.utils import CursorWrapper
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Project

from .models import SiteSettings
from .views import error_400, error_403, error_500


def update_settings(**fields):
    SiteSettings.objects.filter(pk=1).update(**fields)


def make_project(title, slug, category, **fields):
    return Project.objects.create(
        title=title,
        slug=slug,
        short_description=f"{title} summary.",
        description="Details.",
        category=category,
        is_published=fields.pop("is_published", True),
        **fields,
    )


class FaviconTests(TestCase):
    def test_root_favicon_is_served_directly(self):
        response = self.client.get("/favicon.ico", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/x-icon")
        self.assertIn("max-age", response["Cache-Control"])
        self.assertGreater(len(response.content), 100)


class ServerErrorPageTests(TestCase):
    def request(self):
        return RequestFactory().get("/", secure=True)

    @override_settings(PUBLIC_CONTACT_EMAIL="help@example.com")
    def test_500_page_is_standalone_and_needs_no_database(self):
        with self.assertNumQueries(0):
            response = error_500(self.request())

        self.assertEqual(response.status_code, 500)
        content = response.content.decode()
        self.assertIn("Something went wrong.", content)
        self.assertIn("help@example.com", content)
        self.assertIn('name="robots" content="noindex"', content)
        # No site chrome: it would need the database and static files.
        self.assertNotIn("Skip to content", content)
        self.assertNotIn("site-navigation", content)

    def test_500_page_still_renders_when_every_database_query_fails(self):
        with patch.object(CursorWrapper, "execute", side_effect=RuntimeError("database is down")):
            response = error_500(self.request())

        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong.", response.content.decode())

    def test_500_page_does_not_expose_configuration_or_tracebacks(self):
        content = error_500(self.request()).content.decode()

        for secret in ("DATABASE_URL", "SECRET_KEY", "Traceback"):
            self.assertNotIn(secret, content)

    def test_a_broken_template_falls_back_to_a_plain_page(self):
        with patch("core.views.render_to_string", side_effect=RuntimeError("template broke")):
            response = error_500(self.request())

        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong.", response.content.decode())

    def test_400_page_is_standalone(self):
        response = error_400(self.request(), Exception("bad"))

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "That request could not be understood.", status_code=400)

    def test_a_disallowed_host_gets_the_friendly_400_page(self):
        response = self.client.get("/", HTTP_HOST="evil.example.com", secure=True)

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "could not be understood", status_code=400)


class NotFoundPageTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="NF Cat", slug="nf-cat")
        self.inactive = Category.objects.create(name="NF Off", slug="nf-off", is_active=False)

    def test_page_uses_the_text_from_site_settings(self):
        update_settings(not_found_heading="Nothing lives here.", not_found_message="Try the search box.")

        response = self.client.get("/no-such-page/", secure=True)

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Nothing lives here.", status_code=404)
        self.assertContains(response, "Try the search box.", status_code=404)

    def test_page_is_not_indexed_and_has_a_search_box(self):
        response = self.client.get("/no-such-page/", secure=True)

        self.assertContains(response, '<meta name="robots" content="noindex, follow">', status_code=404)
        self.assertContains(response, 'role="search"', status_code=404)
        self.assertContains(response, f'action="{reverse("pages:project_catalogue")}', status_code=404)

    def test_popular_projects_show_only_public_ones_and_at_most_three(self):
        for number in range(4):
            make_project(f"Shown {number}", f"shown-{number}", self.category, featured=number == 0)
        make_project("Draft Project", "draft-project", self.category, is_published=False)
        make_project("Hidden Category Project", "hidden-cat", self.inactive)

        response = self.client.get("/no-such-page/", secure=True)

        self.assertContains(response, "Popular projects", status_code=404)
        self.assertContains(response, "Shown 0", status_code=404)
        self.assertNotContains(response, "Draft Project", status_code=404)
        self.assertNotContains(response, "Hidden Category Project", status_code=404)
        self.assertEqual(response.content.decode().count('class="related-row"'), 3)

    def test_page_without_projects_has_no_popular_section(self):
        response = self.client.get("/no-such-page/", secure=True)

        self.assertNotContains(response, "Popular projects", status_code=404)

    def test_a_project_with_a_broken_image_does_not_break_the_page(self):
        project = make_project("Broken Image", "broken-image", self.category)
        Project.objects.filter(pk=project.pk).update(thumbnail="projectvybe/missing")

        response = self.client.get("/no-such-page/", secure=True)

        self.assertContains(response, "Broken Image", status_code=404)


class CsrfAndForbiddenPageTests(TestCase):
    def test_expired_form_shows_a_friendly_page_with_status_403(self):
        client = Client(enforce_csrf_checks=True)

        response = client.post(reverse("leads:enquiry"), {"name": "x"}, secure=True)

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403_csrf.html")
        self.assertContains(response, "That form has expired.", status_code=403)
        self.assertContains(response, "Nothing was submitted", status_code=403)
        self.assertContains(response, '<meta name="robots" content="noindex, follow">', status_code=403)
        self.assertNotContains(response, "Reason given for failure", status_code=403)

    def test_permission_denied_page(self):
        response = error_403(RequestFactory().get("/", secure=True), Exception("no"))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "You do not have access", status_code=403)


class MaintenanceModeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="ops", password="a-long-test-password-123", is_staff=True
        )

    def test_visitors_see_a_503_page_with_the_message(self):
        update_settings(maintenance_enabled=True, maintenance_message="Upgrading the servers.")

        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Upgrading the servers.", status_code=503)
        self.assertContains(response, 'name="robots" content="noindex"', status_code=503)
        self.assertEqual(response["Retry-After"], "3600")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_every_public_page_and_form_is_covered(self):
        update_settings(maintenance_enabled=True)

        for url in ("/projects/", "/services/", "/about/", reverse("leads:enquiry"), "/privacy/"):
            self.assertEqual(self.client.get(url, secure=True).status_code, 503, url)
        post = self.client.post(reverse("leads:enquiry"), {"name": "x"}, secure=True)
        self.assertEqual(post.status_code, 503)

    def test_expected_return_time_is_shown_and_sets_retry_after(self):
        update_settings(
            maintenance_enabled=True,
            maintenance_return_time=timezone.now() + timedelta(hours=2),
        )

        response = self.client.get("/", secure=True)

        self.assertContains(response, "Expected back", status_code=503)
        self.assertTrue(7000 <= int(response["Retry-After"]) <= 7201)

    def test_a_return_time_in_the_past_falls_back_to_the_default_retry(self):
        update_settings(
            maintenance_enabled=True,
            maintenance_return_time=timezone.now() - timedelta(hours=1),
        )

        self.assertEqual(self.client.get("/", secure=True)["Retry-After"], "3600")

    def test_staff_can_still_browse_the_site(self):
        update_settings(maintenance_enabled=True)
        self.client.force_login(self.staff)

        self.assertEqual(self.client.get("/", secure=True).status_code, 200)

    def test_admin_health_check_robots_and_sitemap_stay_available(self):
        update_settings(maintenance_enabled=True)

        self.assertEqual(self.client.get(reverse("admin:login"), secure=True).status_code, 200)
        self.assertEqual(self.client.get("/health/", secure=True).status_code, 200)
        self.assertEqual(self.client.get("/robots.txt", secure=True).status_code, 200)
        self.assertEqual(self.client.get("/sitemap.xml", secure=True).status_code, 200)

    def test_switching_it_off_restores_the_site_immediately(self):
        update_settings(maintenance_enabled=True)
        self.assertEqual(self.client.get("/", secure=True).status_code, 503)

        update_settings(maintenance_enabled=False)

        self.assertEqual(self.client.get("/", secure=True).status_code, 200)

    def test_off_by_default(self):
        self.assertEqual(self.client.get("/", secure=True).status_code, 200)

    def test_a_settings_read_failure_does_not_take_the_site_down(self):
        # The middleware cannot tell whether maintenance is on, so it must fail open
        # and let the normal page (and its own error handling) take over.
        with patch("core.middleware.get_site_settings", side_effect=RuntimeError("db down")):
            response = self.client.get("/about/", secure=True)

        self.assertEqual(response.status_code, 200)
