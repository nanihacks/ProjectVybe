from decimal import Decimal

from django.core.cache import cache
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Project, ProjectAddon
from core.faq import faqs_for
from core.models import Faq, SiteSettings


def make_faq(question="Is it free?", answer="No.", **flags):
    defaults = {
        "show_on_home": False,
        "show_on_projects": False,
        "show_on_services": False,
        "show_on_contact": False,
        "show_on_courses": False,
    }
    defaults.update(flags)
    return Faq.objects.create(question=question, answer=answer, **defaults)


class SeedTests(TestCase):
    def test_migration_seeds_starter_faqs_and_social_links(self):
        self.assertGreaterEqual(Faq.objects.count(), 5)
        self.assertTrue(SiteSettings.get_solo().instagram_url.startswith("https://"))


class FaqTests(TestCase):
    def setUp(self):
        Faq.objects.all().delete()  # drop the starter FAQs seeded by the migration
        cache.clear()

    def test_faqs_for_filters_by_page_and_published_state(self):
        make_faq("On home", show_on_home=True)
        make_faq("On projects", show_on_projects=True)
        make_faq("Hidden", show_on_home=True, is_published=False)
        self.assertEqual([f.question for f in faqs_for("home")], ["On home"])
        self.assertEqual([f.question for f in faqs_for("projects")], ["On projects"])
        self.assertEqual(faqs_for("services"), [])

    def test_unknown_placement_is_an_error(self):
        with self.assertRaises(ValueError):
            faqs_for("nowhere")

    def test_order_field_controls_the_order(self):
        make_faq("Second", show_on_home=True, ordering=20)
        make_faq("First", show_on_home=True, ordering=10)
        self.assertEqual([f.question for f in faqs_for("home")], ["First", "Second"])

    def test_faqs_show_on_the_ticked_pages_only(self):
        make_faq("Shown on home?", "Yes it is.", show_on_home=True)
        make_faq("Shown on contact?", "Yes it is too.", show_on_contact=True)
        self.assertContains(self.client.get(reverse("pages:home")), "Shown on home?")
        self.assertNotContains(self.client.get(reverse("pages:home")), "Shown on contact?")
        self.assertContains(self.client.get(reverse("leads:enquiry")), "Shown on contact?")
        self.assertNotContains(self.client.get(reverse("pages:services")), "Shown on home?")

    def test_project_page_shows_project_faqs_with_json_ld(self):
        category = Category.objects.create(name="AI", slug="ai-faq")
        project = Project.objects.create(
            title="P", slug="p-faq", short_description="s", description="d", category=category, is_published=True
        )
        make_faq("What do I get?", "The source code.\n\nAnd a guide.", show_on_projects=True)
        response = self.client.get(reverse("pages:project_detail", args=[project.slug]))
        self.assertContains(response, "What do I get?")
        self.assertContains(response, "<p>The source code.</p>", html=True)
        self.assertContains(response, '"@type": "FAQPage"')

    def test_nothing_is_rendered_without_faqs(self):
        response = self.client.get(reverse("pages:home"))
        self.assertNotContains(response, "faq-item")
        self.assertNotContains(response, "FAQPage")

    def test_html_in_a_faq_is_escaped(self):
        make_faq("<b>Bold?</b>", "<script>alert(1)</script>", show_on_home=True)
        response = self.client.get(reverse("pages:home"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;b&gt;Bold?&lt;/b&gt;")

    @override_settings(FAQ_CACHE_SECONDS=300)
    def test_saving_a_faq_clears_the_cache(self):
        faq = make_faq("Old", show_on_home=True)
        self.assertEqual([f.question for f in faqs_for("home")], ["Old"])
        faq.question = "New"
        faq.save()
        self.assertEqual([f.question for f in faqs_for("home")], ["New"])
        faq.delete()
        self.assertEqual(faqs_for("home"), [])

    @override_settings(FAQ_CACHE_SECONDS=300)
    def test_cached_faqs_cost_no_further_queries(self):
        make_faq("Cached", show_on_home=True)
        faqs_for("home")
        with self.assertNumQueries(0):
            faqs_for("home")


class SocialLinkTests(TestCase):
    def update(self, **fields):
        site = SiteSettings.get_solo()
        for name, value in fields.items():
            setattr(site, name, value)
        site.save()

    def test_placeholder_links_are_seeded_and_shown_as_icons(self):
        home = self.client.get(reverse("pages:home"))
        for label in ("Instagram", "LinkedIn", "YouTube", "GitHub", "Facebook", "X (Twitter)"):
            self.assertContains(home, f'aria-label="{label}"')
        self.assertContains(home, "site-footer__social")

    def test_a_blank_link_is_not_shown(self):
        self.update(facebook_url="", x_url="")
        home = self.client.get(reverse("pages:home"))
        self.assertNotContains(home, 'aria-label="Facebook"')
        self.assertNotContains(home, 'aria-label="X (Twitter)"')
        self.assertContains(home, 'aria-label="Instagram"')

    def test_links_open_safely_in_a_new_tab(self):
        self.update(instagram_url="https://instagram.com/mine")
        self.assertContains(self.client.get(reverse("pages:home")), 'href="https://instagram.com/mine" rel="noopener noreferrer" target="_blank"')

    @override_settings(WHATSAPP_NUMBER="919876543210")
    def test_whatsapp_icon_uses_the_server_number(self):
        self.assertContains(self.client.get(reverse("pages:home")), 'href="https://wa.me/919876543210"')

    @override_settings(WHATSAPP_NUMBER="")
    def test_no_whatsapp_icon_without_a_number(self):
        self.update(whatsapp_number="")
        self.assertNotContains(self.client.get(reverse("pages:home")), "https://wa.me/")


class IconAndTextTagTests(SimpleTestCase):
    def render(self, source, **context):
        return Template("{% load icons textutils %}" + source).render(Context(context))

    def test_known_icon_renders_an_accessible_decorative_svg(self):
        html = self.render('{% icon "mail" 18 %}')
        self.assertIn("<svg", html)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('width="18"', html)

    def test_unknown_icon_renders_nothing(self):
        self.assertEqual(self.render('{% icon "nope" %}'), "")

    def test_split_dots_and_initial_filters(self):
        self.assertEqual(self.render("{{ v|split_dots|join:'|' }}", v="AI/ML · Web, Security | Mobile"), "AI/ML|Web|Security|Mobile")
        self.assertEqual(self.render("{{ v|initial }}", v="praveen"), "P")
        self.assertEqual(self.render("{{ v|initial }}", v=""), "")


class AddonPanelTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="AI", slug="ai-addon-panel")
        self.project = Project.objects.create(
            title="Panel Project", slug="panel-project", short_description="s", description="d",
            category=category, is_published=True, price=Decimal("1000"), accept_online_payment=True,
        )
        self.priced = ProjectAddon.objects.create(name="Report", slug="report-panel", price=Decimal("250"), is_popular=True, inclusions="A\nB\nC\nD")
        self.unpriced = ProjectAddon.objects.create(name="Mentoring", slug="mentoring-panel")
        self.project.addons.add(self.priced, self.unpriced)

    def test_whatsapp_mode_shows_prices_and_an_ask_link_without_checkboxes(self):
        response = self.client.get(reverse("pages:project_detail", args=[self.project.slug]))
        self.assertContains(response, "+₹250")
        self.assertContains(response, "Popular")
        self.assertContains(response, f"addon={self.unpriced.slug}")
        self.assertNotContains(response, 'class="addon2__input"')
        self.assertNotContains(response, "data-addons-continue")
