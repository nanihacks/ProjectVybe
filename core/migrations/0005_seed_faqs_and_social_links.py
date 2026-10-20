from django.db import migrations


# Placeholder links so the footer icons show up. Replace them in Admin > Site settings.
SOCIAL_DEFAULTS = {
    "instagram_url": "https://www.instagram.com/projectvybe/",
    "linkedin_url": "https://www.linkedin.com/company/projectvybe/",
    "youtube_url": "https://www.youtube.com/@projectvybe",
    "github_url": "https://github.com/projectvybe",
    "facebook_url": "https://www.facebook.com/projectvybe",
    "x_url": "https://x.com/projectvybe",
}

# (question, answer, home, projects, services, contact, courses)
FAQS = [
    (
        "How do I get a project?",
        "Open the project you like and use the button on its page. If online payment is available you can pay "
        "and choose how you want to receive it. Otherwise send us a short enquiry and we will reply on WhatsApp or email.",
        True, True, False, True, False,
    ),
    (
        "Can a project be changed to fit my requirements?",
        "Yes. Describe the changes you need when you enquire, and we confirm the scope and the price before any work starts.",
        False, True, True, False, False,
    ),
    (
        "Are add-ons available?",
        "Many projects have optional add-ons such as documentation or presentation support. They are listed on the "
        "project page with their prices, and you can pick them when you buy or enquire.",
        False, True, False, False, False,
    ),
    (
        "How will I receive my order?",
        "You choose email, WhatsApp or a Google Drive link. The delivery time is shown on the project page and in "
        "your confirmation email.",
        True, True, False, False, False,
    ),
    (
        "Is there a demo?",
        "Projects with a demo video have a play button on their page. If you want to see something specific, "
        "ask us and we will tell you what we can show.",
        False, True, False, False, False,
    ),
    (
        "Can I get a refund?",
        "Projects are digital, so payments are generally not refundable. If something went wrong, send a refund "
        "request with your order reference and we review it fairly. The Refund Policy explains the details.",
        True, True, False, True, False,
    ),
    (
        "Who are the services for?",
        "Students, developers and small teams who want practical help with projects, documentation, mentorship or "
        "software development.",
        False, False, True, False, False,
    ),
    (
        "How quickly will you reply?",
        "We usually reply within one working day, by WhatsApp or email.",
        False, False, True, True, False,
    ),
    (
        "Do you offer courses?",
        "Courses are being planned. Join the waitlist on the Courses page and we will email you when one opens.",
        True, False, False, True, True,
    ),
]


def seed(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    Faq = apps.get_model("core", "Faq")
    database = schema_editor.connection.alias

    site = SiteSettings.objects.using(database).first()
    if site is not None:
        changed = []
        for field, url in SOCIAL_DEFAULTS.items():
            if not getattr(site, field):
                setattr(site, field, url)
                changed.append(field)
        if changed:
            site.save(update_fields=changed)

    if not Faq.objects.using(database).exists():
        for order, (question, answer, home, projects, services, contact, courses) in enumerate(FAQS, start=1):
            Faq.objects.using(database).create(
                question=question,
                answer=answer,
                show_on_home=home,
                show_on_projects=projects,
                show_on_services=services,
                show_on_contact=contact,
                show_on_courses=courses,
                ordering=order * 10,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_faq_and_social"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
