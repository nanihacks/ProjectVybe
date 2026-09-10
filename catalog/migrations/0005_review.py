from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_category_homepage_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="Review",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reviewer_name", models.CharField(max_length=120)),
                (
                    "reviewer_role",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Optional role, course, or project context shown "
                            "below the review."
                        ),
                        max_length=160,
                    ),
                ),
                ("message", models.TextField()),
                ("is_published", models.BooleanField(default=False)),
                ("ordering", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["ordering", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["is_published", "ordering"],
                        name="catalog_rev_is_publ_76e561_idx",
                    )
                ],
            },
        ),
    ]
