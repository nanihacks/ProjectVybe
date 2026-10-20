import datetime

from django.db import migrations

from legal.rendering import render_markdown
from legal.seed_content import POLICIES


def seed_legal_pages(apps, schema_editor):
    LegalPage = apps.get_model("legal", "LegalPage")
    LegalPageVersion = apps.get_model("legal", "LegalPageVersion")
    database = schema_editor.connection.alias

    for policy in POLICIES:
        page, created = LegalPage.objects.using(database).get_or_create(
            slug=policy["slug"],
            defaults={
                "title": policy["title"],
                "hero_copy": policy["hero_copy"],
                "seo_description": policy["seo_description"],
                "body_markdown": policy["body_markdown"],
                "footer_label": policy["footer_label"],
                "footer_order": policy["footer_order"],
                "show_in_footer": True,
                "is_published": True,
            },
        )
        if not created:
            # Never overwrite a page that already exists.
            continue
        LegalPageVersion.objects.using(database).create(
            page=page,
            number=1,
            effective_date=datetime.date.fromisoformat(policy["effective_date"]),
            change_note="Initial version",
            body_markdown=policy["body_markdown"],
            body_html=render_markdown(policy["body_markdown"]),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("legal", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_legal_pages, migrations.RunPython.noop),
    ]
