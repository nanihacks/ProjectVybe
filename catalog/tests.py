from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from cloudinary.models import CloudinaryField

from .models import Category, Project, ProjectAddon, ProjectImage, Service


class CatalogModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Artificial Intelligence",
            slug="artificial-intelligence",
        )

    def test_category_creation_defaults_and_string_representation(self):
        self.assertTrue(self.category.is_active)
        self.assertIsNotNone(self.category.created_at)
        self.assertEqual(str(self.category), "Artificial Intelligence")

    def test_category_slugs_are_unique(self):
        with self.assertRaises(IntegrityError):
            Category.objects.create(
                name="Duplicate Category",
                slug="artificial-intelligence",
            )

    def test_project_creation_relationship_and_defaults(self):
        project = Project.objects.create(
            title="Example Project",
            slug="example-project",
            short_description="A real project description.",
            description="Detailed project information.",
            category=self.category,
        )

        self.assertEqual(project.category, self.category)
        self.assertFalse(project.is_published)
        self.assertFalse(project.featured)
        self.assertEqual(list(project.addons.all()), [])
        self.assertIsNotNone(project.created_at)
        self.assertIsNotNone(project.updated_at)
        self.assertEqual(str(project), "Example Project")

    def test_project_addons_can_be_assigned(self):
        addon = ProjectAddon.objects.create(
            name="Documentation support",
            slug="catalog-test-documentation",
            description="Project documentation support.",
        )
        project = Project.objects.create(
            title="Project Addons Project",
            slug="project-addons-project",
            short_description="A project with optional add-ons.",
            description="Details about the project.",
            category=self.category,
        )
        project.addons.add(addon)

        self.assertEqual(list(project.addons.all()), [addon])

    def test_default_project_addons_are_available_after_migration(self):
        self.assertEqual(
            set(ProjectAddon.objects.values_list("slug", flat=True)),
            {"documentation", "presentation", "publication", "mentorship"},
        )

    def test_project_slugs_are_unique(self):
        Project.objects.create(
            title="First Project",
            slug="same-slug",
            short_description="Description one.",
            description="Details one.",
            category=self.category,
        )

        with self.assertRaises(IntegrityError):
            Project.objects.create(
                title="Second Project",
                slug="same-slug",
                short_description="Description two.",
                description="Details two.",
                category=self.category,
            )

    def test_invalid_youtube_url_fails_validation(self):
        project = Project(
            title="Video Project",
            slug="video-project",
            short_description="Description.",
            description="Details.",
            youtube_demo_url="https://example.com/video",
            category=self.category,
        )

        with self.assertRaises(ValidationError):
            project.full_clean()

    def test_project_image_relationship_and_string_representation(self):
        project = Project.objects.create(
            title="Gallery Project",
            slug="gallery-project",
            short_description="A project with a gallery.",
            description="Gallery project details.",
            category=self.category,
        )
        image = ProjectImage.objects.create(
            project=project,
            image="projects/gallery/one",
            alt_text="Gallery project screen",
            ordering=1,
        )

        self.assertEqual(list(project.gallery_images.all()), [image])
        self.assertEqual(image.ordering, 1)
        self.assertEqual(str(image), f"Gallery Project image {image.pk}")

    def test_service_creation_defaults_and_string_representation(self):
        service = Service.objects.create(
            name="Documentation",
            slug="documentation",
            short_description="Documentation support.",
            description="Documentation service details.",
        )

        self.assertTrue(service.is_active)
        self.assertEqual(service.ordering, 0)
        self.assertEqual(str(service), "Documentation")


class CloudinaryConfigurationTests(TestCase):
    def test_image_fields_are_cloudinary_fields(self):
        self.assertIsInstance(Category._meta.get_field("image"), CloudinaryField)
        self.assertIsInstance(Project._meta.get_field("thumbnail"), CloudinaryField)
        self.assertIsInstance(ProjectImage._meta.get_field("image"), CloudinaryField)
        self.assertIsInstance(Service._meta.get_field("image"), CloudinaryField)

    def test_cloudinary_asset_folders_are_configured(self):
        category = Category(name="Computer Vision", slug="computer-vision")
        project = Project(slug="asset-project")
        project_image = ProjectImage(project=project)
        service = Service(name="Training", slug="training")

        category_folder = Category._meta.get_field("image").options["asset_folder"]
        project_folder = Project._meta.get_field("thumbnail").options["asset_folder"]
        gallery_folder = ProjectImage._meta.get_field("image").options["asset_folder"]
        service_folder = Service._meta.get_field("image").options["asset_folder"]

        self.assertEqual(category_folder(category), "projectvybe/categories")
        self.assertEqual(project_folder(project), "projectvybe/projects/asset-project")
        self.assertEqual(gallery_folder(project_image), "projectvybe/projects/asset-project")
        self.assertEqual(service_folder(service), "projectvybe/services")

    def test_cloudinary_delivery_is_secure_and_credentials_are_environment_based(self):
        self.assertTrue(settings.CLOUDINARY["secure"])
        self.assertEqual(settings.CLOUDINARY_URL, "")

    def test_catalog_models_are_registered_in_default_admin(self):
        self.assertIn(Category, admin.site._registry)
        self.assertIn(Project, admin.site._registry)
        self.assertIn(ProjectAddon, admin.site._registry)
        self.assertIn(Service, admin.site._registry)
