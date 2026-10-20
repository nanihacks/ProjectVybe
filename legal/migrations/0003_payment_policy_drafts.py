from django.db import migrations

from legal.payment_content import UPDATES, updated_draft


def update_drafts(apps, schema_editor):
    """Put the online-payment wording into the DRAFT of four pages.

    Only a page whose draft still equals its latest published version is touched, so a
    draft someone has already started editing in Admin is left alone. Nothing is
    published: the live pages do not change until Publish is pressed.
    """
    LegalPage = apps.get_model("legal", "LegalPage")
    LegalPageVersion = apps.get_model("legal", "LegalPageVersion")
    database = schema_editor.connection.alias

    for slug in UPDATES:
        page = LegalPage.objects.using(database).filter(slug=slug).first()
        if page is None:
            continue
        latest = LegalPageVersion.objects.using(database).filter(page=page).order_by("-number").first()
        if latest is None or page.body_markdown != latest.body_markdown:
            continue
        page.body_markdown = updated_draft(slug, page.body_markdown)
        page.save(update_fields=["body_markdown"])


class Migration(migrations.Migration):
    dependencies = [
        ("legal", "0002_seed_legal_pages"),
    ]

    operations = [
        migrations.RunPython(update_drafts, migrations.RunPython.noop),
    ]
