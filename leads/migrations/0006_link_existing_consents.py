from django.db import migrations


def link_existing_consents(apps, schema_editor):
    """Point consent records made before versioning at Privacy Policy v1."""
    ConsentRecord = apps.get_model("leads", "ConsentRecord")
    LegalPageVersion = apps.get_model("legal", "LegalPageVersion")
    database = schema_editor.connection.alias

    first_version = (
        LegalPageVersion.objects.using(database)
        .filter(page__slug="privacy-policy", number=1)
        .first()
    )
    if first_version is None:
        return
    ConsentRecord.objects.using(database).filter(
        privacy_policy__isnull=True,
        privacy_policy_version="2026-10-18",
    ).update(
        privacy_policy=first_version,
        privacy_policy_version=f"v{first_version.number} ({first_version.effective_date.isoformat()})",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("leads", "0005_consent_policy_version_link"),
        ("legal", "0002_seed_legal_pages"),
    ]

    operations = [
        migrations.RunPython(link_existing_consents, migrations.RunPython.noop),
    ]
