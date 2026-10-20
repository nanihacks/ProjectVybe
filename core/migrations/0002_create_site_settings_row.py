from django.db import migrations


def create_site_settings_row(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.using(schema_editor.connection.alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_site_settings"),
    ]

    operations = [
        # Create the single row up front so reading it never has to insert.
        migrations.RunPython(create_site_settings_row, migrations.RunPython.noop),
    ]
