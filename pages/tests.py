import json
import re
from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Project, ProjectAddon, ProjectImage, Review, Service
from pages.views import _safe_cloudinary_url, _youtube_embed_url


class HomePageTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/home.html")
        self.assertContains(response, "Build. Learn. Grow.")
        self.assertContains(response, "css/base.css")
        self.assertContains(response, "css/components.css")
        self.assertContains(response, "ProjectVybe")
        self.assertContains(response, "Projects")
        self.assertContains(response, "Services")
        self.assertContains(response, "Contact")
        self.assertContains(response, "Skip to content")

    def test_home_page_uses_limited_catalogue_queries(self):
        with self.assertNumQueries(4):
            response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)


class HomePageContentTests(TestCase):
    def setUp(self):
        self.active_category = Category.objects.create(
            name="Active Category",
            slug="active-category",
            description="A category shown on the homepage.",
            is_active=True,
        )
        Category.objects.create(
            name="Inactive Category",
            slug="inactive-category",
            description="A category hidden from the homepage.",
            is_active=False,
        )

        Project.objects.create(
            title="Published Featured Project",
            slug="published-featured-project",
            short_description="A published featured project.",
            description="Project description.",
            category=self.active_category,
            featured=True,
            is_published=True,
        )
        Project.objects.create(
            title="Published Non Featured Project",
            slug="published-non-featured-project",
            short_description="A published project that is not featured.",
            description="Project description.",
            category=self.active_category,
            featured=False,
            is_published=True,
        )
        Project.objects.create(
            title="Unpublished Featured Project",
            slug="unpublished-featured-project",
            short_description="A project not ready for public display.",
            description="Project description.",
            category=self.active_category,
            featured=True,
            is_published=False,
        )

        Service.objects.create(
            name="Active Service",
            slug="active-service",
            short_description="An active service.",
            description="Service description.",
            is_active=True,
        )
        Service.objects.create(
            name="Inactive Service",
            slug="inactive-service",
            short_description="An inactive service.",
            description="Service description.",
            is_active=False,
        )
        Review.objects.create(
            reviewer_name="Published reviewer",
            reviewer_role="Student project support",
            message="ProjectVybe made the next step clear.",
            is_published=True,
        )
        Review.objects.create(
            reviewer_name="Hidden reviewer",
            message="This review should not be displayed.",
            is_published=False,
        )

    def test_homepage_shows_only_active_categories_featured_projects_and_services(self):
        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active Category")
        self.assertNotContains(response, "Inactive Category")
        self.assertContains(response, 'class="card card--category"')
        self.assertContains(response, 'data-category-carousel')
        self.assertContains(response, 'data-category-scroller')
        self.assertContains(response, 'data-category-prev')
        self.assertContains(response, 'data-category-next')
        self.assertContains(
            response,
            f'href="{reverse("pages:project_catalogue")}?category=active-category#project-results-title"',
        )
        self.assertContains(response, "Published Featured Project")
        self.assertNotContains(response, "Published Non Featured Project")
        self.assertNotContains(response, "Unpublished Featured Project")
        self.assertContains(response, "Active Service")
        self.assertNotContains(response, "Inactive Service")
        self.assertContains(response, "Published reviewer")
        self.assertContains(response, "ProjectVybe made the next step clear.")
        self.assertContains(response, 'data-review-carousel')
        self.assertContains(response, 'data-review-prev')
        self.assertContains(response, 'data-review-next')
        self.assertContains(response, 'data-review-scroller')
        self.assertNotContains(response, "Hidden reviewer")

    def test_homepage_ctas_point_to_existing_destinations(self):
        response = self.client.get("/", secure=True)
        home_url = reverse("pages:home")

        self.assertContains(response, f'href="{home_url}#projects"')
        self.assertContains(response, f'href="{reverse("pages:services")}"')
        self.assertContains(response, f'href="{reverse("leads:enquiry")}"')

    def test_projects_navigation_dropdown_uses_active_categories(self):
        response = self.client.get("/", secure=True)

        self.assertContains(response, "Browse by category")
        self.assertContains(
            response,
            f'href="{reverse("pages:project_catalogue")}?category=active-category#project-results-title"',
        )
        self.assertNotContains(response, "inactive-category")


class HomePageEmptyContentTests(TestCase):
    def test_empty_content_has_honest_empty_states(self):
        response = self.client.get("/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project categories are being prepared.")
        self.assertContains(response, "Featured projects will appear here.")
        self.assertContains(response, "Services will appear here as they are published.")


class ProjectCatalogueTests(TestCase):
    def setUp(self):
        self.active_category = Category.objects.create(
            name="Active Catalogue Category",
            slug="active-catalogue-category",
        )
        self.other_active_category = Category.objects.create(
            name="Other Active Category",
            slug="other-active-category",
        )
        self.inactive_category = Category.objects.create(
            name="Inactive Catalogue Category",
            slug="inactive-catalogue-category",
            is_active=False,
        )

        for index in range(10):
            title = f"Catalogue Project {index:02d}"
            if index == 0:
                title = "Python Catalogue Project 00"
            Project.objects.create(
                title=title,
                slug=f"catalogue-project-{index:02d}",
                short_description=f"Published catalogue project {index}.",
                description=f"Details for published catalogue project {index}.",
                technology_stack="Python\nDjango" if index == 0 else "Django",
                category=self.active_category,
                is_published=True,
            )

        Project.objects.create(
            title="Python Other Category Project",
            slug="python-other-category-project",
            short_description="A published project in another active category.",
            description="Details for another active category project.",
            technology_stack="Python",
            category=self.other_active_category,
            is_published=True,
        )
        Project.objects.create(
            title="Inactive Category Project",
            slug="inactive-category-project",
            short_description="A project in an inactive category.",
            description="This project must not be publicly listed.",
            category=self.inactive_category,
            is_published=True,
        )
        Project.objects.create(
            title="Hidden Draft Project",
            slug="hidden-draft-project",
            short_description="An unpublished project.",
            description="This project must not be publicly listed.",
            category=self.active_category,
            is_published=False,
        )

    def test_catalogue_shows_published_projects_and_active_categories_only(self):
        response = self.client.get(reverse("pages:project_catalogue"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/projects.html")
        self.assertContains(response, "Catalogue Project 09")
        self.assertContains(response, "Active Catalogue Category")
        self.assertNotContains(response, "Hidden Draft Project")
        self.assertNotContains(response, "Inactive Category Project")
        self.assertNotContains(response, "Inactive Catalogue Category")
        self.assertNotContains(response, 'aria-label="Breadcrumb"')

    def test_search_is_case_insensitive_and_only_returns_published_projects(self):
        response = self.client.get(
            reverse("pages:project_catalogue"),
            {"q": "PYTHON"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python Catalogue Project 00")
        self.assertContains(response, "Python Other Category Project")
        self.assertNotContains(response, "Hidden Draft Project")

    def test_live_project_search_returns_public_matching_projects_as_json(self):
        response = self.client.get(
            reverse("pages:project_search"),
            {"q": "PYTHON"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = response.json()
        titles = [result["title"] for result in payload["results"]]
        self.assertIn("Python Catalogue Project 00", titles)
        self.assertIn("Python Other Category Project", titles)
        self.assertNotIn("Hidden Draft Project", titles)

    def test_live_project_search_empty_query_returns_empty_results(self):
        response = self.client.get(reverse("pages:project_search"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"query": "", "results": []})

    def test_category_filter_and_invalid_category_are_safe(self):
        response = self.client.get(
            reverse("pages:project_catalogue"),
            {"category": self.active_category.slug},
            secure=True,
        )

        self.assertEqual(response.context["page_obj"].paginator.count, 10)
        self.assertContains(response, "Catalogue Project 09")
        self.assertNotContains(response, "Python Other Category Project")

        inactive_response = self.client.get(
            reverse("pages:project_catalogue"),
            {"category": self.inactive_category.slug},
            secure=True,
        )
        invalid_response = self.client.get(
            reverse("pages:project_catalogue"),
            {"category": "does-not-exist"},
            secure=True,
        )

        self.assertEqual(inactive_response.status_code, 200)
        self.assertIsNone(inactive_response.context["selected_category"])
        self.assertContains(inactive_response, "Catalogue Project 09")
        self.assertNotContains(inactive_response, "Inactive Category Project")
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "Catalogue Project 09")

    def test_search_and_category_filters_are_composable(self):
        response = self.client.get(
            reverse("pages:project_catalogue"),
            {"q": "python", "category": self.active_category.slug},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python Catalogue Project 00")
        self.assertNotContains(response, "Python Other Category Project")

    def test_pagination_preserves_search_and_category_filters(self):
        response = self.client.get(
            reverse("pages:project_catalogue"),
            {"q": "project", "category": self.active_category.slug},
            secure=True,
        )

        self.assertEqual(len(response.context["page_obj"].object_list), 9)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertContains(
            response,
            "q=project&amp;category=active-catalogue-category&amp;page=2",
        )

        next_response = self.client.get(
            reverse("pages:project_catalogue"),
            {
                "q": "project",
                "category": self.active_category.slug,
                "page": 2,
            },
            secure=True,
        )

        self.assertEqual(next_response.status_code, 200)
        self.assertEqual(next_response.context["page_obj"].number, 2)
        self.assertEqual(len(next_response.context["page_obj"].object_list), 1)
        self.assertContains(
            next_response,
            "q=project&amp;category=active-catalogue-category&amp;page=1",
        )

    def test_project_cards_link_to_published_project_detail_pages(self):
        response = self.client.get(reverse("pages:project_catalogue"), secure=True)
        detail_url = reverse(
            "pages:project_detail",
            kwargs={"slug": "catalogue-project-09"},
        )

        self.assertContains(response, f'href="{detail_url}"')

        detail_response = self.client.get(detail_url, secure=True)
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "pages/project_detail.html")

        unpublished_url = reverse(
            "pages:project_detail",
            kwargs={"slug": "hidden-draft-project"},
        )
        self.assertEqual(self.client.get(unpublished_url, secure=True).status_code, 404)


class ProjectCatalogueEmptyStateTests(TestCase):
    def test_empty_catalogue_has_a_clear_empty_state(self):
        with self.assertNumQueries(2):
            response = self.client.get(reverse("pages:project_catalogue"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projects are being added soon.")
        self.assertContains(response, "Check back shortly")

    def test_empty_search_has_a_search_specific_empty_state(self):
        response = self.client.get(
            reverse("pages:project_catalogue"),
            {"q": "no-match"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No projects matched your search.")
        self.assertContains(response, "View all projects")


class ProjectDetailTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Detail Category",
            slug="detail-category",
        )
        self.other_category = Category.objects.create(
            name="Other Detail Category",
            slug="other-detail-category",
        )
        self.inactive_category = Category.objects.create(
            name="Inactive Detail Category",
            slug="inactive-detail-category",
            is_active=False,
        )
        self.project = Project.objects.create(
            title="Published Detail Project",
            slug="published-detail-project",
            short_description="A published project for detail-page tests.",
            description="This is the project overview.\nIt has useful context.",
            usage="This project can support a practical project use case.",
            features="Feature one\nFeature two",
            technology_stack="Python\nDjango",
            requirements="A suitable development environment.",
            thumbnail="projects/detail/thumbnail",
            youtube_demo_url="https://www.youtube.com/watch?v=abcdefghijk",
            category=self.category,
            is_published=True,
        )
        self.documentation_addon = ProjectAddon.objects.create(
            name="Documentation support",
            slug="detail-documentation-addon",
            description="Documentation support for this project.",
            ordering=10,
        )
        self.mentorship_addon = ProjectAddon.objects.create(
            name="1:1 mentorship",
            slug="detail-mentorship-addon",
            description="One-to-one mentorship for this project.",
            ordering=20,
        )
        self.inactive_addon = ProjectAddon.objects.create(
            name="Inactive project add-on",
            slug="inactive-detail-addon",
            description="An inactive project add-on.",
            is_active=False,
            ordering=30,
        )
        self.project.addons.add(
            self.documentation_addon,
            self.mentorship_addon,
            self.inactive_addon,
        )
        ProjectImage.objects.create(
            project=self.project,
            image="projects/detail/second",
            alt_text="Second project view",
            ordering=2,
        )
        ProjectImage.objects.create(
            project=self.project,
            image="projects/detail/first",
            alt_text="First project view",
            ordering=1,
        )
        self.same_category_project = Project.objects.create(
            title="Same Category Project",
            slug="same-category-project",
            short_description="Another published project in the same category.",
            description="Related project details.",
            category=self.category,
            is_published=True,
        )
        self.other_category_project = Project.objects.create(
            title="Other Category Project",
            slug="other-category-project",
            short_description="Another published project.",
            description="Other related project details.",
            category=self.other_category,
            is_published=True,
        )
        self.unpublished_project = Project.objects.create(
            title="Unpublished Related Project",
            slug="unpublished-related-project",
            short_description="An unpublished project.",
            description="This must not be exposed.",
            category=self.category,
            is_published=False,
        )
        self.inactive_category_project = Project.objects.create(
            title="Inactive Category Detail Project",
            slug="inactive-category-detail-project",
            short_description="A project in an inactive category.",
            description="This must not be exposed.",
            category=self.inactive_category,
            is_published=True,
        )
        Service.objects.create(
            name="Active Detail Service",
            slug="active-detail-service",
            short_description="An active service for detail enquiries.",
            description="Active service details.",
            is_active=True,
        )
        Service.objects.create(
            name="Inactive Detail Service",
            slug="inactive-detail-service",
            short_description="An inactive service.",
            description="Inactive service details.",
            is_active=False,
        )

    def detail_url(self, slug=None):
        return reverse(
            "pages:project_detail",
            kwargs={"slug": slug or self.project.slug},
        )

    def test_published_detail_renders_project_information_and_gallery(self):
        response = self.client.get(self.detail_url(), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/project_detail.html")
        self.assertContains(response, "Published Detail Project")
        self.assertContains(response, "Detail Category")
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, "This is the project overview.")
        self.assertContains(response, "practical project use case")
        self.assertContains(response, "A suitable development environment.")
        self.assertContains(response, "Feature one")
        self.assertContains(response, "Feature two")
        self.assertContains(response, "Python")
        self.assertContains(response, "Django")
        self.assertContains(response, "First project view")
        self.assertContains(response, "Second project view")
        self.assertEqual(
            [image.alt_text for image in response.context["gallery_images"]],
            ["First project view", "Second project view"],
        )

    def test_unpublished_nonexistent_and_inactive_category_projects_return_404(self):
        unpublished_response = self.client.get(
            self.detail_url(self.unpublished_project.slug),
            secure=True,
        )
        missing_response = self.client.get(
            self.detail_url("does-not-exist"),
            secure=True,
        )
        inactive_response = self.client.get(
            self.detail_url(self.inactive_category_project.slug),
            secure=True,
        )

        self.assertEqual(unpublished_response.status_code, 404)
        self.assertNotIn(b"Unpublished Related Project", unpublished_response.content)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(inactive_response.status_code, 404)

    def test_demo_cta_is_present_only_when_a_demo_url_exists(self):
        response = self.client.get(self.detail_url(), secure=True)
        self.assertContains(response, "Watch demo")
        self.assertContains(
            response,
            'data-video-url="https://www.youtube-nocookie.com/embed/abcdefghijk?rel=0"',
        )
        self.assertContains(response, 'data-video-open')
        self.assertNotContains(response, 'target="_blank"')

        self.project.youtube_demo_url = ""
        self.project.save(update_fields=["youtube_demo_url"])
        response_without_demo = self.client.get(self.detail_url(), secure=True)
        self.assertNotContains(response_without_demo, "Watch demo")

    def test_project_enquiry_cta_starts_structured_enquiry_flow(self):
        response = self.client.get(self.detail_url(), secure=True)

        self.assertContains(response, "Get this project")
        self.assertContains(response, 'href="#project-enquiry"')
        self.assertContains(response, 'data-enquiry-open')
        self.assertContains(response, 'id="project-enquiry"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "Step 1 of 2")
        self.assertContains(response, "Continue to WhatsApp")

    @override_settings(WHATSAPP_NUMBER="")
    def test_missing_whatsapp_configuration_does_not_break_detail_page(self):
        response = self.client.get(self.detail_url(), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "wa.me")
        self.assertContains(response, "Explore more projects")

    def test_project_addons_are_separate_from_company_services(self):
        response = self.client.get(self.detail_url(), secure=True)

        self.assertContains(response, "Documentation support")
        self.assertContains(response, "1:1 mentorship")
        self.assertNotContains(response, "Inactive project add-on")
        self.assertNotContains(response, "Active Detail Service")
        self.assertNotContains(response, "Inactive Detail Service")
        self.assertNotContains(response, "Ask about this add-on")

    def test_related_projects_prefer_same_category_and_exclude_unpublished_or_current(self):
        response = self.client.get(self.detail_url(), secure=True)
        related_projects = response.context["related_projects"]

        self.assertIn(self.same_category_project, related_projects)
        self.assertIn(self.other_category_project, related_projects)
        self.assertNotIn(self.project, related_projects)
        self.assertNotIn(self.unpublished_project, related_projects)
        self.assertNotIn(self.inactive_category_project, related_projects)


class ProjectDetailEmptyContentTests(TestCase):
    def setUp(self):
        category = Category.objects.create(
            name="Empty Detail Category",
            slug="empty-detail-category",
        )
        self.project = Project.objects.create(
            title="Empty Content Project",
            slug="empty-content-project",
            short_description="A project without optional detail content.",
            description="A basic project description.",
            category=category,
            is_published=True,
        )

    def test_detail_handles_missing_optional_content_and_images(self):
        response = self.client.get(
            reverse(
                "pages:project_detail",
                kwargs={"slug": self.project.slug},
            ),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project image coming soon")
        self.assertNotContains(response, "Project media")
        self.assertNotContains(response, "Key features")
        self.assertNotContains(response, "Technology stack")
        self.assertNotContains(response, "Watch demo")
        self.assertNotContains(response, "Additional support")
        self.assertContains(response, "Explore more projects")


class ServicesPageTests(TestCase):
    def setUp(self):
        Service.objects.create(
            name="Later Service",
            slug="later-service",
            short_description="A service shown after the first service.",
            description="Later service details.",
            ordering=2,
            is_active=True,
        )
        Service.objects.create(
            name="First Service",
            slug="first-service",
            short_description="A service shown first.",
            description="First service details.",
            ordering=1,
            is_active=True,
        )
        Service.objects.create(
            name="Hidden Service",
            slug="hidden-service",
            short_description="This service is not public.",
            description="Hidden service details.",
            ordering=0,
            is_active=False,
        )

    def test_services_page_shows_active_services_in_admin_order(self):
        response = self.client.get(reverse("pages:services"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/services.html")
        self.assertContains(response, "Practical support for technology work.")
        self.assertContains(response, "First Service")
        self.assertContains(response, "A service shown first.")
        self.assertContains(response, "Later Service")
        self.assertNotContains(response, 'aria-label="Breadcrumb"')
        self.assertNotContains(response, "Hidden Service")
        self.assertLess(
            response.content.find(b"First Service"),
            response.content.find(b"Later Service"),
        )

    def test_service_cards_start_service_specific_enquiries(self):
        response = self.client.get(reverse("pages:services"), secure=True)

        self.assertContains(
            response,
            f'href="{reverse("leads:enquiry")}?service=first-service"',
        )
        self.assertContains(response, "Enquire about this service")

    def test_services_navigation_marks_current_page(self):
        response = self.client.get(reverse("pages:services"), secure=True)

        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, f'href="{reverse("pages:about")}"')

    def test_services_page_uses_catalogue_and_navigation_queries(self):
        with self.assertNumQueries(2):
            response = self.client.get(reverse("pages:services"), secure=True)

        self.assertEqual(response.status_code, 200)


class ServicesPageEmptyStateTests(TestCase):
    def test_services_page_has_a_clear_empty_state(self):
        response = self.client.get(reverse("pages:services"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Services are being updated.")
        self.assertContains(response, "Contact ProjectVybe")


class AboutPageTests(TestCase):
    def setUp(self):
        Category.objects.create(
            name="Active About Category",
            slug="active-about-category",
            description="An active category for the About page.",
            is_active=True,
        )
        Category.objects.create(
            name="Hidden About Category",
            slug="hidden-about-category",
            description="This category is not public.",
            is_active=False,
        )

    def test_about_page_renders_positioning_and_active_categories(self):
        response = self.client.get(reverse("pages:about"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/about.html")
        self.assertContains(response, "Build. Learn. Grow.")
        self.assertContains(response, "A place for practical technology progress.")
        self.assertContains(response, "Active About Category")
        self.assertNotContains(response, "Hidden About Category")
        self.assertContains(response, 'data-category-carousel')
        self.assertContains(response, 'data-category-scroller')
        self.assertContains(response, 'data-category-prev')
        self.assertContains(response, 'data-category-next')
        self.assertNotContains(response, 'aria-label="Breadcrumb"')

    def test_about_page_ctas_and_category_links_use_existing_routes(self):
        response = self.client.get(reverse("pages:about"), secure=True)

        self.assertContains(
            response,
            f'href="{reverse("pages:project_catalogue")}"',
        )
        self.assertContains(
            response,
            f'href="{reverse("leads:enquiry")}"',
        )
        self.assertContains(
            response,
            f'href="{reverse("pages:project_catalogue")}?category=active-about-category#project-results-title"',
        )

    def test_about_navigation_marks_current_page(self):
        response = self.client.get(reverse("pages:about"), secure=True)

        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, f'href="{reverse("pages:services")}"')

    def test_about_page_uses_one_catalogue_query(self):
        with self.assertNumQueries(1):
            response = self.client.get(reverse("pages:about"), secure=True)

        self.assertEqual(response.status_code, 200)


class AboutPageEmptyStateTests(TestCase):
    def test_about_page_has_a_clear_category_empty_state(self):
        response = self.client.get(reverse("pages:about"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project categories are being prepared.")


class CloudinaryDeliveryTests(SimpleTestCase):
    def test_delivery_transform_is_render_only_and_conservative(self):
        class CloudinaryResource:
            public_id = "projects/example/thumbnail"
            url = "https://res.cloudinary.com/demo/image/upload/v1/projects/example/thumbnail"

            def build_url(self, **options):
                self.options = options
                return "https://res.cloudinary.com/demo/image/upload/c_limit,f_auto,q_auto,w_640/v1/projects/example/thumbnail"

        resource = CloudinaryResource()
        transformed_url = _safe_cloudinary_url(resource, width=640)

        self.assertIn("f_auto", transformed_url)
        self.assertIn("q_auto", transformed_url)
        self.assertIn("w_640", transformed_url)
        self.assertEqual(resource.options["transformation"]["crop"], "limit")
        self.assertEqual(resource.public_id, "projects/example/thumbnail")

    def test_delivery_transform_falls_back_to_original_url(self):
        class CloudinaryResource:
            public_id = "projects/example/thumbnail"
            url = "https://res.cloudinary.com/demo/image/upload/v1/projects/example/thumbnail"

            def build_url(self, **options):
                raise ValueError("Cloudinary configuration unavailable")

        self.assertEqual(
            _safe_cloudinary_url(CloudinaryResource(), width=640),
            "https://res.cloudinary.com/demo/image/upload/v1/projects/example/thumbnail",
        )


class YouTubeEmbedUrlTests(SimpleTestCase):
    def test_watch_url_becomes_privacy_enhanced_embed_url(self):
        self.assertEqual(
            _youtube_embed_url("https://www.youtube.com/watch?v=abcdefghijk"),
            "https://www.youtube-nocookie.com/embed/abcdefghijk?rel=0",
        )

    def test_short_url_becomes_privacy_enhanced_embed_url(self):
        self.assertEqual(
            _youtube_embed_url("https://youtu.be/abcdefghijk"),
            "https://www.youtube-nocookie.com/embed/abcdefghijk?rel=0",
        )

    def test_unknown_or_invalid_url_does_not_create_an_embed(self):
        self.assertEqual(_youtube_embed_url("https://example.com/video"), "")
        self.assertEqual(_youtube_embed_url("https://www.youtube.com/watch?v=short"), "")


class PolicyPageTests(TestCase):
    policy_pages = (
        ("privacy_policy", "pages/privacy.html", "Privacy Policy", "Information you may submit"),
        ("terms", "pages/terms.html", "Terms &amp; Conditions", "Enquiries and communication"),
        (
            "refund_policy",
            "pages/refund_policy.html",
            "Refund / Cancellation Policy",
            "Enquiries are not online transactions",
        ),
        ("cookies", "pages/cookies.html", "Cookie Policy", "Necessary cookies"),
    )

    def test_policy_routes_render_expected_templates_and_content(self):
        for url_name, template_name, title, content in self.policy_pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(f"pages:{url_name}"), secure=True)

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template_name)
                self.assertContains(response, title)
                self.assertContains(response, content)
                self.assertContains(response, "support@projectvybe.com")

    def test_footer_contains_working_links_to_all_policy_pages(self):
        response = self.client.get(reverse("pages:privacy_policy"), secure=True)

        for url_name in ("privacy_policy", "terms", "refund_policy", "cookies"):
            with self.subTest(url_name=url_name):
                self.assertContains(
                    response,
                    f'href="{reverse(f"pages:{url_name}")}"',
                )


class SeoMetadataTests(TestCase):
    @override_settings(SITE_URL="https://seo.example.com///")
    def test_canonical_and_open_graph_urls_use_normalized_configured_origin(self):
        response = self.client.get(
            reverse("pages:home"),
            secure=True,
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'rel="canonical" href="https://seo.example.com/"',
        )
        self.assertContains(
            response,
            'property="og:url" content="https://seo.example.com/"',
        )
        self.assertNotContains(response, "localhost")
        self.assertNotContains(response, "seo.example.com//")
        self.assertContains(response, "AI, ML &amp; Software Projects | ProjectVybe")
        self.assertContains(response, 'name="description"')

    @override_settings(SITE_URL="http://localhost:8000/")
    def test_local_site_url_is_used_without_request_host(self):
        response = self.client.get(
            reverse("pages:about"),
            HTTP_HOST="127.0.0.1",
        )

        self.assertContains(
            response,
            'rel="canonical" href="http://localhost:8000/about/"',
        )
        self.assertContains(
            response,
            'property="og:url" content="http://localhost:8000/about/"',
        )

    def test_filtered_project_catalogue_is_noindex_with_base_canonical(self):
        response = self.client.get(
            reverse("pages:project_catalogue"),
            {"q": "search-term"},
            secure=True,
        )

        self.assertContains(response, 'name="robots" content="noindex, follow"')
        self.assertContains(
            response,
            f'rel="canonical" href="http://localhost:8000{reverse("pages:project_catalogue")}"',
        )

    def test_enquiry_page_is_noindex_but_followable(self):
        response = self.client.get(reverse("leads:enquiry"), secure=True)

        self.assertContains(response, 'name="robots" content="noindex, follow"')
        self.assertNotContains(response, 'aria-label="Breadcrumb"')

    def test_homepage_json_ld_contains_only_real_site_data(self):
        response = self.client.get(reverse("pages:home"), secure=True)
        match = re.search(
            rb'<script type="application/ld\+json">(.*?)</script>',
            response.content,
            re.DOTALL,
        )

        self.assertIsNotNone(match)
        structured_data = json.loads(match.group(1))
        self.assertEqual(structured_data["@type"], "WebSite")
        self.assertEqual(structured_data["url"], "http://localhost:8000/")


class SitemapAndRobotsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.active_category = Category.objects.create(
            name="SEO Category",
            slug="seo-category",
            is_active=True,
        )
        cls.published_project = Project.objects.create(
            title="Published SEO Project",
            slug="published-seo-project",
            short_description="A published project for sitemap tests.",
            description="Published project details.",
            category=cls.active_category,
            is_published=True,
        )
        Project.objects.create(
            title="Unpublished SEO Project",
            slug="unpublished-seo-project",
            short_description="A project excluded from public indexing.",
            description="Unpublished project details.",
            category=cls.active_category,
            is_published=False,
        )

    @override_settings(SITE_URL="https://seo.example.com///")
    def test_robots_txt_uses_configured_sitemap_url_and_public_rules(self):
        response = self.client.get(
            reverse("pages:robots_txt"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, "Allow: /")
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Disallow: /enquiry/success/")
        self.assertContains(response, "Sitemap: https://seo.example.com/sitemap.xml")
        self.assertNotContains(response, "seo.example.com//")
        self.assertNotContains(response, "localhost")

    @override_settings(SITE_URL="https://seo.example.com/")
    def test_sitemap_includes_public_pages_and_published_projects_only(self):
        response = self.client.get(
            reverse("sitemap"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://seo.example.com/")
        self.assertContains(response, "https://seo.example.com/privacy/")
        self.assertContains(
            response,
            "https://seo.example.com/projects/published-seo-project/",
        )
        self.assertNotContains(
            response,
            "https://seo.example.com/projects/unpublished-seo-project/",
        )
        self.assertNotContains(response, "/enquiry/")
        self.assertNotContains(response, "localhost")


class ProjectSeoTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Project SEO Category",
            slug="project-seo-category",
        )
        self.project = Project.objects.create(
            title="Searchable Project",
            slug="searchable-project",
            short_description="A real project description for social metadata.",
            description="Project details.",
            thumbnail="projects/seo/searchable-project",
            category=self.category,
            is_published=True,
        )

    @override_settings(SITE_URL="https://seo.example.com///")
    def test_published_project_uses_canonical_image_and_truthful_structured_data(self):
        with patch(
            "pages.views._safe_cloudinary_url",
            return_value="https://res.cloudinary.com/demo/image/upload/projects/seo/searchable-project",
        ):
            response = self.client.get(
                reverse(
                    "pages:project_detail",
                    kwargs={"slug": self.project.slug},
                ),
                HTTP_HOST="localhost",
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Searchable Project | ProjectVybe")
        self.assertContains(
            response,
            'rel="canonical" href="https://seo.example.com/projects/searchable-project/"',
        )
        self.assertContains(response, 'property="og:type" content="article"')
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, 'name="twitter:image"')
        self.assertContains(response, "CreativeWork")
        self.assertContains(response, "BreadcrumbList")


class ErrorPageTests(TestCase):
    def test_missing_route_uses_the_public_404_template(self):
        response = self.client.get("/this-route-does-not-exist/", secure=True)

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "That page could not be found.", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)


class DesignSystemTemplateTests(SimpleTestCase):
    def test_reusable_breadcrumb_component_renders_accessible_markup(self):
        rendered = render_to_string(
            "components/breadcrumbs.html",
            {
                "breadcrumbs": [
                    {"label": "Projects", "url": "/projects/"},
                    {"label": "Example project"},
                ]
            },
        )

        self.assertIn('aria-label="Breadcrumb"', rendered)
        self.assertIn("Projects", rendered)
        self.assertIn('aria-current="page"', rendered)

    def test_component_templates_are_available(self):
        for template_name in (
            "components/navbar.html",
            "components/footer.html",
            "components/messages.html",
            "components/buttons.html",
            "components/cards/project_card.html",
            "components/cards/service_card.html",
            "components/cards/addon_card.html",
            "components/cards/category_card.html",
            "components/forms/form_field.html",
            "components/forms/project_enquiry_modal.html",
        ):
            rendered = render_to_string(template_name)
            self.assertIsInstance(rendered, str)

    def test_design_system_static_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/base.css"))
        self.assertIsNotNone(finders.find("css/components.css"))
        self.assertIsNotNone(finders.find("js/site.js"))
