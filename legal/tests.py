from unittest import mock
import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import SiteSettings
from core.testing import force_login_verified

from .models import LegalPage, LegalPageVersion
from .rendering import fill_placeholders, render_markdown
from .services import current_privacy_version, footer_links


def make_page(slug="custom-policy", publish=True, **fields):
    defaults = {
        "title": "Custom Policy",
        "slug": slug,
        "hero_copy": "A custom policy.",
        "body_markdown": "Intro paragraph.\n\n## First heading\n\nBody text.",
        "is_published": True,
        "show_in_footer": True,
    }
    defaults.update(fields)
    page = LegalPage.objects.create(**defaults)
    if publish:
        page.publish()
    return page


class MarkdownRenderingTests(SimpleTestCase):
    def test_headings_lists_and_emphasis_are_rendered(self):
        html = render_markdown("## Heading\n\n- one\n- two\n\n**bold** and *italic*")

        self.assertIn("<h2>Heading</h2>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)

    def test_scripts_event_handlers_and_unsafe_links_are_removed(self):
        html = render_markdown(
            "<script>alert(1)</script>\n\n"
            "[bad](javascript:alert(1)) and [data](data:text/html;base64,AAAA)\n\n"
            '<img src=x onerror="alert(1)"> <iframe src="https://evil.example"></iframe>\n\n'
            '<a href="https://ok.example" onclick="alert(1)">fine</a>'
        )

        self.assertNotIn("<script", html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("data:text", html)
        self.assertNotIn("onerror", html)
        self.assertNotIn("onclick", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("<img", html)
        self.assertIn('href="https://ok.example"', html)

    def test_links_get_a_safe_rel_and_only_known_schemes_survive(self):
        html = render_markdown("[web](https://a.example) [mail](mailto:a@b.example) [local](/privacy/)")

        self.assertIn('href="https://a.example"', html)
        self.assertIn('href="mailto:a@b.example"', html)
        self.assertIn('href="/privacy/"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_tables_are_allowed(self):
        html = render_markdown("| A | B |\n|---|---|\n| 1 | 2 |")

        self.assertIn("<table>", html)
        self.assertIn("<td>1</td>", html)


class PlaceholderTests(SimpleTestCase):
    VALUES = {
        "contact_email": "help@example.com",
        "legal_name": "Example <b>LLP</b>",
        "registered_address": "1 Main St",
        "grievance_officer_name": "Asha",
        "grievance_officer_email": "asha@example.com",
        "whatsapp_number": "911111111111",
    }

    def test_placeholders_are_filled(self):
        html = fill_placeholders(
            '<a href="mailto:{contact_email}">{contact_email}</a> {grievance_officer_name}',
            self.VALUES,
        )

        self.assertEqual(
            html,
            '<a href="mailto:help@example.com">help@example.com</a> Asha',
        )

    def test_values_are_escaped_so_they_cannot_inject_markup(self):
        html = fill_placeholders("<p>{legal_name}</p>", self.VALUES)

        self.assertEqual(html, "<p>Example &lt;b&gt;LLP&lt;/b&gt;</p>")

    def test_unknown_braces_are_left_alone(self):
        self.assertEqual(fill_placeholders("<p>{not_a_placeholder}</p>", self.VALUES), "<p>{not_a_placeholder}</p>")


PAYMENT_DRAFT_SLUGS = {"privacy-policy", "terms-and-conditions", "refund-policy", "shipping-delivery-policy"}


class SeededPagesTests(TestCase):
    def test_all_pages_are_seeded_published_with_a_first_version(self):
        slugs = {
            "privacy-policy": datetime.date(2026, 10, 18),
            "terms-and-conditions": datetime.date(2026, 9, 9),
            "refund-policy": datetime.date(2026, 9, 9),
            "cookie-policy": datetime.date(2026, 9, 9),
            "grievance-redressal": datetime.date(2026, 10, 19),
            "shipping-delivery-policy": datetime.date(2026, 10, 19),
            "academic-integrity-policy": datetime.date(2026, 10, 19),
        }
        for slug, effective in slugs.items():
            with self.subTest(slug=slug):
                page = LegalPage.objects.get(slug=slug)
                self.assertTrue(page.is_published)
                self.assertTrue(page.show_in_footer)
                version = page.latest_version
                self.assertEqual(version.number, 1)
                self.assertEqual(version.effective_date, effective)
                # The online-payment wording waits in the draft of these four pages.
                self.assertEqual(page.has_unpublished_changes(), slug in PAYMENT_DRAFT_SLUGS)

    def test_payment_drafts_do_not_change_the_live_pages(self):
        refund = LegalPage.objects.get(slug="refund-policy")
        self.assertIn("Enquiries are not online transactions", refund.latest_version.body_markdown)
        self.assertIn("non-refundable", refund.body_markdown)
        self.assertIn("/orders/refund-request/", refund.body_markdown)
        terms = LegalPage.objects.get(slug="terms-and-conditions")
        self.assertIn("## Online purchases", terms.body_markdown)
        self.assertNotIn("## Online purchases", terms.latest_version.body_markdown)
        self.assertIn("8 years", LegalPage.objects.get(slug="privacy-policy").body_markdown)
        self.assertIn("within 2 hours", LegalPage.objects.get(slug="shipping-delivery-policy").body_markdown)

    def test_draft_migration_leaves_an_edited_draft_alone(self):
        import importlib

        from django.apps import apps as global_apps

        migration = importlib.import_module("legal.migrations.0003_payment_policy_drafts")
        LegalPage.objects.filter(slug="refund-policy").update(body_markdown="My own edit")
        migration.update_drafts(global_apps, mock.Mock(connection=mock.Mock(alias="default")))
        self.assertEqual(LegalPage.objects.get(slug="refund-policy").body_markdown, "My own edit")

    def test_seeded_pages_use_the_site_settings_placeholders_not_hard_coded_emails(self):
        for page in LegalPage.objects.all():
            self.assertNotIn("support@projectvybe.com", page.body_markdown, page.slug)

    def test_privacy_policy_points_to_the_privacy_request_form_and_grievance_page(self):
        privacy = LegalPage.objects.get(slug="privacy-policy").body_markdown

        self.assertIn("/privacy/request/", privacy)
        self.assertIn("/grievance-redressal/", privacy)


class PublishingTests(TestCase):
    def test_editing_the_draft_does_not_change_the_live_page(self):
        page = make_page()
        page.body_markdown = "Changed draft text."
        page.save()

        response = self.client.get(page.get_absolute_url(), secure=True)

        self.assertContains(response, "Body text.")
        self.assertNotContains(response, "Changed draft text.")
        self.assertTrue(page.has_unpublished_changes())

    def test_publishing_creates_the_next_version_and_goes_live(self):
        page = make_page()
        page.body_markdown = "New policy text."
        page.save()

        version = page.publish(effective_date=datetime.date(2026, 11, 1), change_note="Rewrote")

        self.assertEqual(version.number, 2)
        self.assertEqual(version.change_note, "Rewrote")
        self.assertEqual(page.versions.count(), 2)
        response = self.client.get(page.get_absolute_url(), secure=True)
        self.assertContains(response, "New policy text.")
        self.assertContains(response, "Last updated: November 1, 2026")

    def test_old_versions_keep_their_original_text(self):
        page = make_page()
        original = page.latest_version.body_markdown
        page.body_markdown = "Something else entirely."
        page.save()
        page.publish()

        self.assertEqual(page.versions.get(number=1).body_markdown, original)

    def test_publishing_an_unchanged_draft_does_nothing(self):
        page = make_page()

        self.assertIsNone(page.publish())
        self.assertEqual(page.versions.count(), 1)

    def test_published_by_records_the_staff_member(self):
        user = get_user_model().objects.create_user(username="editor", password="a-long-test-password-123")
        page = make_page(publish=False)

        version = page.publish(user=user)

        self.assertEqual(version.published_by, user)

    def test_version_html_is_sanitised_when_published(self):
        page = make_page(body_markdown="Hi\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1))")

        self.assertNotIn("<script", page.latest_version.body_html)
        self.assertNotIn("javascript:", page.latest_version.body_html)


class PublicViewTests(TestCase):
    def test_unpublished_page_is_a_404_even_with_versions(self):
        page = make_page(is_published=False)

        self.assertEqual(self.client.get(page.get_absolute_url(), secure=True).status_code, 404)

    def test_page_without_a_published_version_is_a_404(self):
        page = make_page(publish=False)

        self.assertEqual(self.client.get(page.get_absolute_url(), secure=True).status_code, 404)

    def test_new_pages_are_served_under_legal_slug(self):
        page = make_page()

        self.assertEqual(page.get_absolute_url(), "/legal/custom-policy/")
        response = self.client.get("/legal/custom-policy/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2>First heading</h2>")
        self.assertContains(response, "A custom policy.")

    def test_pages_with_their_own_address_redirect_from_the_generic_one(self):
        response = self.client.get("/legal/privacy-policy/", secure=True)

        self.assertRedirects(response, "/privacy/", status_code=301, fetch_redirect_response=False)

    def test_canonical_url_points_to_the_page_address(self):
        response = self.client.get(reverse("pages:terms"), secure=True)

        self.assertContains(response, 'rel="canonical" href="http://localhost:8000/terms/"')

    def test_site_settings_values_appear_without_republishing(self):
        page = make_page(body_markdown="Write to [{contact_email}](mailto:{contact_email}). Run by {legal_name}.")
        SiteSettings.objects.filter(pk=1).update(contact_email="first@example.com", legal_name="First LLP")
        self.assertContains(self.client.get(page.get_absolute_url(), secure=True), "first@example.com")

        SiteSettings.objects.filter(pk=1).update(contact_email="second@example.com", legal_name="Second LLP")
        response = self.client.get(page.get_absolute_url(), secure=True)

        self.assertContains(response, 'href="mailto:second@example.com"')
        self.assertContains(response, "Run by Second LLP.")
        self.assertNotContains(response, "first@example.com")

    def test_site_settings_values_are_escaped_in_the_page(self):
        page = make_page(body_markdown="Run by {legal_name}.")
        SiteSettings.objects.filter(pk=1).update(legal_name="<script>alert(1)</script>")

        response = self.client.get(page.get_absolute_url(), secure=True)

        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_blank_site_settings_fall_back_to_sensible_text(self):
        page = make_page(body_markdown="By {legal_name}.")

        response = self.client.get(page.get_absolute_url(), secure=True)

        self.assertContains(response, "By ProjectVybe.")

    def test_list_items_with_a_blank_detail_are_left_out(self):
        page = make_page(
            body_markdown=(
                "Intro.\n\n- Name: {grievance_officer_name}\n"
                "- Address: {registered_address}\n- Business: {legal_name}"
            )
        )
        SiteSettings.objects.filter(pk=1).update(registered_address="  ", grievance_officer_name="")

        response = self.client.get(page.get_absolute_url(), secure=True)

        self.assertNotContains(response, "Address:")
        self.assertNotContains(response, "Name:")
        self.assertContains(response, "<li>Business: ProjectVybe</li>")

    def test_list_items_with_a_filled_detail_are_kept(self):
        page = make_page(body_markdown="Intro.\n\n- Address: {registered_address}")
        SiteSettings.objects.filter(pk=1).update(registered_address="1 Main St")

        self.assertContains(self.client.get(page.get_absolute_url(), secure=True), "<li>Address: 1 Main St</li>")

    def test_seeded_grievance_page_reads_well_before_details_are_entered(self):
        response = self.client.get(reverse("pages:grievance_redressal"), secure=True)

        self.assertNotContains(response, "Address:")
        self.assertNotContains(response, "Name:")
        self.assertContains(response, "Please write to our Grievance Officer:")


class FooterLinkTests(TestCase):
    def test_footer_lists_published_pages_in_order_with_labels(self):
        LegalPage.objects.all().delete()
        make_page("zeta", title="Zeta", footer_order=2, footer_label="Second link")
        make_page("alpha", title="Alpha", footer_order=1)

        links = footer_links()

        self.assertEqual(links, [("Alpha", "/legal/alpha/"), ("Second link", "/legal/zeta/")])

    def test_hidden_unpublished_and_unversioned_pages_are_left_out(self):
        LegalPage.objects.all().delete()
        make_page("shown", title="Shown")
        make_page("hidden", title="Hidden", show_in_footer=False)
        make_page("draft", title="Draft", is_published=False)
        make_page("empty", title="Empty", publish=False)

        self.assertEqual([label for label, _ in footer_links()], ["Shown"])

    @override_settings(LEGAL_FOOTER_CACHE_SECONDS=300)
    def test_footer_cache_is_cleared_when_a_page_changes(self):
        cache.clear()
        LegalPage.objects.all().delete()
        page = make_page("cached", title="Cached")
        self.assertEqual([label for label, _ in footer_links()], ["Cached"])

        page.title = "Renamed"
        page.show_in_footer = False
        page.save()

        self.assertEqual(footer_links(), [])


class SitemapTests(TestCase):
    @override_settings(SITE_URL="https://seo.example.com")
    def test_sitemap_lists_published_legal_pages_only(self):
        make_page("sitemap-page", title="Sitemap page")
        make_page("sitemap-draft", title="Sitemap draft", is_published=False)

        body = self.client.get(reverse("sitemap"), secure=True).content.decode()

        self.assertIn("https://seo.example.com/privacy/", body)
        self.assertIn("https://seo.example.com/grievance-redressal/", body)
        self.assertIn("https://seo.example.com/legal/sitemap-page/", body)
        self.assertNotIn("sitemap-draft", body)
        self.assertIn("<lastmod>", body)


class ConsentVersionLinkTests(TestCase):
    def test_current_privacy_version_is_the_latest_published_one(self):
        privacy = LegalPage.objects.get(slug="privacy-policy")
        privacy.body_markdown += "\n\nExtra clause."
        privacy.save()
        privacy.publish()

        self.assertEqual(current_privacy_version().number, 2)

    def test_unpublished_privacy_policy_gives_no_version(self):
        LegalPage.objects.filter(slug="privacy-policy").update(is_published=False)

        self.assertIsNone(current_privacy_version())


class LegalAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username="legal-admin", email="l@example.com", password="a-long-test-password-123"
        )

    def setUp(self):
        force_login_verified(self.client, self.staff)
        self.page = make_page()

    def form_data(self, **extra):
        data = {
            "title": self.page.title,
            "slug": self.page.slug,
            "hero_copy": self.page.hero_copy,
            "seo_description": "",
            "is_published": "on",
            "body_markdown": "Edited draft text.",
            "show_in_footer": "on",
            "footer_label": "",
            "footer_order": "100",
            "effective_date": "",
            "change_note": "",
            "versions-TOTAL_FORMS": "0",
            "versions-INITIAL_FORMS": "0",
            "versions-MIN_NUM_FORMS": "0",
            "versions-MAX_NUM_FORMS": "0",
        }
        data.update(extra)
        return data

    def change_url(self):
        return reverse("admin:legal_legalpage_change", args=[self.page.pk])

    def test_change_page_shows_draft_and_version_history(self):
        response = self.client.get(self.change_url(), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published versions")
        self.assertContains(response, "Publish this draft as a new version")
        self.assertContains(response, "v1 (")

    def test_saving_without_the_publish_box_only_stores_the_draft(self):
        response = self.client.post(self.change_url(), self.form_data(), secure=True)

        self.assertEqual(response.status_code, 302)
        self.page.refresh_from_db()
        self.assertEqual(self.page.body_markdown, "Edited draft text.")
        self.assertEqual(self.page.versions.count(), 1)
        self.assertNotContains(self.client.get(self.page.get_absolute_url(), secure=True), "Edited draft text.")

    def test_ticking_publish_creates_a_new_live_version(self):
        response = self.client.post(
            self.change_url(),
            self.form_data(publish_now="on", effective_date="2026-12-01", change_note="Edited"),
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        version = self.page.versions.get(number=2)
        self.assertEqual(version.effective_date, datetime.date(2026, 12, 1))
        self.assertEqual(version.change_note, "Edited")
        self.assertEqual(version.published_by, self.staff)
        self.assertContains(self.client.get(self.page.get_absolute_url(), secure=True), "Edited draft text.")

    def test_publish_action_snapshots_changed_drafts_only(self):
        changed = make_page("changed", title="Changed")
        changed.body_markdown = "Fresh text."
        changed.save()

        self.client.post(
            reverse("admin:legal_legalpage_changelist"),
            {"action": "publish_drafts", "_selected_action": [self.page.pk, changed.pk]},
            secure=True,
        )

        self.assertEqual(self.page.versions.count(), 1)
        self.assertEqual(changed.versions.count(), 2)

    def test_versions_cannot_be_edited_through_the_admin(self):
        self.assertTrue(LegalPageVersion.objects.filter(page=self.page).exists())

        response = self.client.get(self.change_url(), secure=True)

        # The history is shown as plain text: no editable inputs for any version field.
        self.assertNotContains(response, 'name="versions-0-body_markdown"')
        self.assertNotContains(response, 'name="versions-0-number"')
        self.assertNotContains(response, 'name="versions-0-change_note"')
