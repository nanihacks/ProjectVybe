from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .admin import (
    CategoryAdmin,
    ProjectAdmin,
    ProjectAddonAdmin,
    ProjectImageInline,
    ServiceAdmin,
    feature_projects,
    publish_projects,
    unfeature_projects,
    unpublish_projects,
)
from .models import Category, Project, ProjectAddon, ProjectImage, Service


class CatalogAdminTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Artificial Intelligence",
            slug="artificial-intelligence",
        )
        Project.objects.bulk_create(
            [
                Project(
                    title="First Project",
                    slug="first-project",
                    short_description="First project.",
                    description="First project details.",
                    category=self.category,
                ),
                Project(
                    title="Second Project",
                    slug="second-project",
                    short_description="Second project.",
                    description="Second project details.",
                    category=self.category,
                ),
            ]
        )

    def test_catalog_models_are_registered_with_expected_admin_classes(self):
        self.assertIsInstance(admin.site._registry[Category], CategoryAdmin)
        self.assertIsInstance(admin.site._registry[Project], ProjectAdmin)
        self.assertIsInstance(admin.site._registry[ProjectAddon], ProjectAddonAdmin)
        self.assertIsInstance(admin.site._registry[Service], ServiceAdmin)

    def test_project_image_inline_is_configured_for_gallery_fields(self):
        self.assertEqual(ProjectImageInline.model, ProjectImage)
        self.assertEqual(ProjectImageInline.fields, ("image", "alt_text", "ordering"))
        self.assertEqual(ProjectImageInline.ordering, ("ordering", "id"))

    def test_project_admin_has_expected_search_filters_and_fieldsets(self):
        project_admin = admin.site._registry[Project]
        self.assertEqual(
            project_admin.search_fields,
            ("title", "slug", "short_description"),
        )
        self.assertIn("category", project_admin.list_filter)
        self.assertIn("is_published", project_admin.list_filter)
        self.assertIn("featured", project_admin.list_filter)
        self.assertEqual(project_admin.filter_horizontal, ("addons",))
        field_names = {
            field_name
            for _, options in project_admin.fieldsets
            for field_name in options["fields"]
        }
        self.assertIn("thumbnail", field_names)
        self.assertIn("youtube_demo_url", field_names)
        self.assertIn("is_published", field_names)
        self.assertIn("addons", field_names)

    def test_project_publish_and_feature_actions_update_selected_projects(self):
        project_admin = ProjectAdmin(Project, admin.site)

        with patch.object(project_admin, "message_user"):
            publish_projects(project_admin, None, Project.objects.all())
            feature_projects(project_admin, None, Project.objects.all())

        self.assertEqual(Project.objects.filter(is_published=True).count(), 2)
        self.assertEqual(Project.objects.filter(featured=True).count(), 2)

    def test_project_unpublish_and_unfeature_actions_update_selected_projects(self):
        Project.objects.update(is_published=True, featured=True)
        project_admin = ProjectAdmin(Project, admin.site)

        with patch.object(project_admin, "message_user"):
            unpublish_projects(project_admin, None, Project.objects.all())
            unfeature_projects(project_admin, None, Project.objects.all())

        self.assertEqual(Project.objects.filter(is_published=True).count(), 0)
        self.assertEqual(Project.objects.filter(featured=True).count(), 0)


class CatalogAdminWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Admin Workflow Category",
            slug="admin-workflow-category",
        )
        cls.first_project = Project.objects.create(
            title="Admin Search Project",
            slug="admin-search-project",
            short_description="Project searchable in admin.",
            description="Admin project details.",
            category=cls.category,
        )
        Project.objects.create(
            title="Other Admin Project",
            slug="other-admin-project",
            short_description="Another admin project.",
            description="Other admin details.",
            category=cls.category,
        )
        user_model = get_user_model()
        cls.admin_user = user_model.objects.create_superuser(
            username="catalog-admin",
            email="catalog-admin@example.com",
            password="test-admin-password",
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_admin_project_changelist_requires_authentication(self):
        self.client.logout()

        response = self.client.get(reverse("admin:catalog_project_changelist"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_authenticated_admin_can_search_projects(self):
        response = self.client.get(
            reverse("admin:catalog_project_changelist"),
            {"q": "searchable"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.first_project.title)
        self.assertNotContains(response, "Other Admin Project")
