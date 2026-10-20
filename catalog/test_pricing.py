from decimal import Decimal

from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase

from .models import Category, Project, ProjectAddon, ProjectAddonPrice, Service
from .pricing import format_inr, to_paise


class FormatInrTests(SimpleTestCase):
    def test_indian_grouping(self):
        cases = {
            0: "₹0",
            7: "₹7",
            999: "₹999",
            1000: "₹1,000",
            12345: "₹12,345",
            124999: "₹1,24,999",
            1234567: "₹12,34,567",
            Decimal("499.5"): "₹499.50",
            Decimal("1999.00"): "₹1,999",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(format_inr(value), expected)

    def test_to_paise_rounds_half_up(self):
        self.assertEqual(to_paise(Decimal("499.50")), 49950)
        self.assertEqual(to_paise(Decimal("0.005")), 1)
        self.assertEqual(to_paise(1), 100)

    def test_inr_filter(self):
        rendered = Template("{% load pricing %}{{ a|inr }}|{{ b|inr }}|{{ c|inr }}").render(
            Context({"a": Decimal("124999"), "b": None, "c": "oops"})
        )
        self.assertEqual(rendered, "₹1,24,999||")


class PriceRulesTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="AI", slug="ai-pricing")

    def project(self, **extra):
        return Project(
            title="P",
            slug=f"p-{Project.objects.count()}",
            short_description="s",
            description="d",
            category=self.category,
            **extra,
        )

    def test_no_price_shows_nothing_and_is_not_purchasable(self):
        project = self.project()
        self.assertFalse(project.has_price)
        self.assertIsNone(project.effective_price)
        self.assertFalse(project.is_purchasable)

    def test_hidden_price_is_not_shown(self):
        project = self.project(price=Decimal("999"), show_price=False)
        self.assertFalse(project.has_price)
        self.assertFalse(project.is_purchasable)

    def test_sale_price_is_effective_price(self):
        project = self.project(price=Decimal("999"), sale_price=Decimal("799"))
        self.assertTrue(project.on_sale)
        self.assertEqual(project.effective_price, Decimal("799"))
        self.assertTrue(project.is_purchasable)

    def test_zero_price_is_not_purchasable(self):
        self.assertFalse(self.project(price=Decimal("0")).is_purchasable)

    def test_sale_price_must_be_lower(self):
        for price, sale in ((Decimal("500"), Decimal("500")), (Decimal("500"), Decimal("600"))):
            with self.subTest(sale=sale), self.assertRaises(ValidationError):
                self.project(price=price, sale_price=sale).clean()

    def test_sale_price_needs_a_price(self):
        with self.assertRaises(ValidationError):
            self.project(sale_price=Decimal("10")).clean()


class PriceDisplayTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="AI", slug="ai-display")

    def make(self, slug, **extra):
        return Project.objects.create(
            title=f"Project {slug}",
            slug=slug,
            short_description="Short.",
            description="Long.",
            category=self.category,
            is_published=True,
            **extra,
        )

    def test_project_page_without_price_has_no_price_markup(self):
        project = self.make("no-price")
        response = self.client.get(f"/projects/{project.slug}/")
        self.assertNotContains(response, 'class="price')
        self.assertNotContains(response, '"offers"')

    def test_project_page_with_price_shows_it_and_offer(self):
        project = self.make("priced", price=Decimal("124999"), price_note="Source code")
        response = self.client.get(f"/projects/{project.slug}/")
        self.assertContains(response, "₹1,24,999")
        self.assertContains(response, "Source code")
        self.assertContains(response, '"offers"')

    def test_sale_price_is_struck_through(self):
        project = self.make("sale", price=Decimal("1000"), sale_price=Decimal("800"))
        response = self.client.get(f"/projects/{project.slug}/")
        self.assertContains(response, "price__was")
        self.assertContains(response, "₹800")

    def test_hidden_price_not_in_page_or_json_ld(self):
        project = self.make("hidden", price=Decimal("500"), show_price=False)
        response = self.client.get(f"/projects/{project.slug}/")
        self.assertNotContains(response, "₹500")
        self.assertNotContains(response, '"offers"')

    def test_service_price_shows_on_services_page(self):
        Service.objects.create(
            name="Mentoring",
            slug="mentoring-price",
            short_description="s",
            description="d",
            price=Decimal("2500"),
            price_prefix="from",
        )
        response = self.client.get("/services/")
        self.assertContains(response, "₹2,500")
        self.assertContains(response, "Starting from")


class AddonPricingTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="AI", slug="ai-addons")
        self.project = Project.objects.create(
            title="P", slug="p-addons", short_description="s", description="d", category=category
        )
        self.addon = ProjectAddon.objects.create(name="Docs", slug="docs-pricing", price=Decimal("999"))
        self.unpriced = ProjectAddon.objects.create(name="Viva", slug="viva-pricing")

    def pricing(self, addon):
        project = Project.objects.prefetch_related("addon_prices").get(pk=self.project.pk)
        return project.addon_pricing(addon)

    def test_default_price(self):
        self.assertEqual(self.pricing(self.addon), (Decimal("999"), False))

    def test_unpriced_addon_has_no_amount(self):
        self.assertEqual(self.pricing(self.unpriced), (None, False))

    def test_project_override_wins(self):
        ProjectAddonPrice.objects.create(project=self.project, addon=self.addon, price_override=Decimal("499"))
        self.assertEqual(self.pricing(self.addon), (Decimal("499"), False))

    def test_included_free(self):
        ProjectAddonPrice.objects.create(project=self.project, addon=self.addon, included_free=True)
        self.assertEqual(self.pricing(self.addon), (Decimal("0"), True))

    def test_override_row_without_values_falls_back_to_default(self):
        ProjectAddonPrice.objects.create(project=self.project, addon=self.addon)
        self.assertEqual(self.pricing(self.addon), (Decimal("999"), False))

    def test_saving_a_price_row_adds_the_addon_to_the_project(self):
        self.assertFalse(self.project.addons.filter(pk=self.addon.pk).exists())
        ProjectAddonPrice.objects.create(project=self.project, addon=self.addon, price_override=Decimal("1"))
        self.assertTrue(self.project.addons.filter(pk=self.addon.pk).exists())
