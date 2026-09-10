# ProjectVybe Production Deployment Plan

This guide deploys ProjectVybe with:

- Render Web Service for Django
- Neon PostgreSQL for production data
- Cloudinary for permanent images
- Resend SMTP for enquiry email delivery
- A custom HTTPS domain

The local SQLite database remains useful for development only. Production must use Neon PostgreSQL through `DATABASE_URL`.

## 1. Current repository deployment readiness

The repository already includes:

- PostgreSQL support through `DATABASE_URL`
- `psycopg` in `requirements.txt`
- Gunicorn in `Procfile`
- WhiteNoise static-file delivery
- Cloudinary model fields for images
- SMTP email configuration
- Production checks that reject SQLite when `DEBUG=False`
- A `/health/` endpoint

Important files:

- [config/settings.py](config/settings.py)
- [requirements.txt](requirements.txt)
- [Procfile](Procfile)
- [build.sh](build.sh)
- [.env.example](.env.example)
- [leads/views.py](leads/views.py)
- [leads/utils.py](leads/utils.py)

## 2. Accounts and services to create

Create these accounts before deployment:

1. GitHub repository containing the project.
2. Render account for the Django web service.
3. Neon account for PostgreSQL.
4. Cloudinary account for images.
5. Resend account for enquiry email delivery.
6. Domain registrar account.
7. A working mailbox such as `support@projectvybe.com`.

Use a separate development/staging database and Cloudinary environment if possible. Never point local development at the production database.

## 3. Pre-deployment local checks

Run from the project root:

```powershell
python manage.py test
python manage.py check
python manage.py collectstatic --noinput
git status
```

Before pushing to GitHub, confirm:

- `.env` is ignored and is not committed.
- No database passwords, API keys, SMTP passwords, or Cloudinary secrets exist in source code.
- All migrations are committed.
- Current content has been reviewed.
- Production-only settings are not stored in `.env.example`.

Generate a new production secret. Do not reuse the local development secret.

## 4. Create the Neon PostgreSQL database

In Neon:

1. Create a project named something like `projectvybe-production`.
2. Select a region close to the Render web service region.
3. Use the production branch for the live website.
4. Click **Connect**.
5. Copy the PostgreSQL connection string.

It should resemble:

```env
postgresql://user:password@ep-example.region.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

Neon documents the standard Python connection format and secure SSL parameters in its [Python connection guide](https://neon.com/docs/guides/python).

### Direct versus pooled Neon connections

For the first deployment, use the direct Neon connection string as `DATABASE_URL`. It is the simplest option for this normal Django/Gunicorn application and is recommended for migrations.

A pooled connection normally contains `-pooler` in its hostname. Use pooled connections later if the application is scaled to several instances or reaches connection limits. Neon recommends a direct connection for ORM migrations and administrative tasks. See [Neon connection pooling](https://neon.com/docs/connect/connection-pooling).

Keep a direct connection available for:

- Django migrations
- Database backups
- `pg_dump`
- Administrative work

## 5. Create the Render Web Service

Connect the GitHub repository to Render and create a Web Service.

Use:

```text
Build command:
bash build.sh

Start command:
gunicorn config.wsgi:application

Health check path:
/health/
```

The build script runs `collectstatic`. Database migrations are intentionally run separately after deployment.

Render's Django deployment instructions are available at [render.com/docs/deploy-django](https://render.com/docs/deploy-django).

## 6. Production environment variables

Set these in Render's environment-variable screen. Do not put real values in Git.

```env
SECRET_KEY=unique-long-production-secret
DEBUG=False

DATABASE_URL=your-neon-direct-connection-string

ALLOWED_HOSTS=your-service.onrender.com
CSRF_TRUSTED_ORIGINS=https://your-service.onrender.com
SITE_URL=https://your-service.onrender.com

SITE_NAME=ProjectVybe
SITE_DESCRIPTION=ProjectVybe helps people build, learn, and grow through thoughtful technology projects and services.

WHATSAPP_NUMBER=your-business-whatsapp-number

CLOUDINARY_URL=cloudinary://api-key:api-secret@cloud-name

PUBLIC_CONTACT_EMAIL=support@projectvybe.com
DEFAULT_FROM_EMAIL=notifications@projectvybe.com

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.resend.com
EMAIL_PORT=587
EMAIL_HOST_USER=resend
EMAIL_HOST_PASSWORD=your-resend-api-key
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=10

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
```

Rules:

- `ALLOWED_HOSTS` contains hostnames only; do not include `https://`.
- `CSRF_TRUSTED_ORIGINS` contains complete HTTPS origins.
- `SITE_URL` contains the canonical public origin without a trailing slash.
- `DEBUG` must be `False` in production.
- Never expose `SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_URL`, or `EMAIL_HOST_PASSWORD`.

## 7. Run migrations and create the admin user

After the first Render deployment, open the Render Shell and run:

```bash
python manage.py migrate --noinput
python manage.py check --deploy
python manage.py createsuperuser
```

Open:

```text
https://your-service.onrender.com/admin/
```

For future code deployments that contain migrations:

```bash
python manage.py migrate --noinput
```

Take a database backup before destructive schema changes.

## 8. Move local SQLite content to Neon

Django migrations copy the schema only. They do not copy records from `db.sqlite3`.

### Option A: Recreate content manually

For a small catalogue, recreate the following through Django Admin:

- Categories
- Projects
- Project add-ons
- Services
- Reviews

This avoids transferring test data and is the safest option for a small initial catalogue.

### Option B: Export catalogue data

Back up SQLite locally:

```powershell
Copy-Item db.sqlite3 db.sqlite3.before-neon.bak
```

Export only the public catalogue app:

```powershell
python manage.py dumpdata catalog `
  --natural-foreign `
  --natural-primary `
  --indent 2 `
  --output catalog-fixture.json
```

This includes categories, projects, galleries, project add-ons, services, and reviews.

Do not export `leads` unless you intentionally want to transfer personal enquiry data. Do not export admin accounts; create a new production superuser instead.

Make the fixture temporarily available to the deployed code, then run in Render Shell:

```bash
python manage.py loaddata catalog-fixture.json
```

After verifying the data:

1. Remove `catalog-fixture.json` from the repository.
2. Push the cleanup commit.
3. Redeploy.

Cloudinary fields store asset references in PostgreSQL. The image files remain in Cloudinary and are not stored inside Neon.

## 9. Configure Cloudinary

In Cloudinary:

1. Create a product environment.
2. Copy the API credentials from the Cloudinary Console.
3. Create the `CLOUDINARY_URL` value.
4. Add it as a secret in Render.
5. Upload images through Django Admin.

The application uses Cloudinary for:

- Category identity images
- Category homepage images
- Project thumbnails
- Project gallery images
- Service images

Cloudinary's Django integration supports `CloudinaryField` uploads through Django forms and Admin. See [Cloudinary Django integration](https://cloudinary.com/documentation/django_integration).

### Recommended image dimensions

The CSS already uses these display ratios:

| Asset | Recommended source size | Ratio | Use |
|---|---:|---:|---|
| Category identity image | `512 × 512 px` | 1:1 | Small category icon/logo in menus and category lists |
| Category homepage image | `1600 × 1000 px` | 16:10 | Large category cards and area sections |
| Project thumbnail | `1600 × 1000 px` | 16:10 | Project cards and project detail hero media |
| Project gallery image | `1600 × 1200 px` | 4:3 | Project detail gallery images |
| Service image | `1600 × 900 px` | 16:9 | Service cards and service detail media |

### Image preparation rules

- Use JPG or WebP for photographs and screenshots.
- Use PNG only when transparency is required.
- Keep the main subject inside the center-safe area because cards use `object-fit: cover`.
- Avoid text close to the edges.
- Use the same ratio for every image in the same field.
- Prefer source files below 2–4 MB; Cloudinary will optimize delivery.
- Use descriptive alt text in Django Admin.
- Do not upload private source code, documents, or PPT files as public images.
- Do not rely on Render's local filesystem for permanent media.

## 10. Add a YouTube project demo

The `Project` model has a `youtube_demo_url` field, and the project detail page displays a **Watch demo on YouTube** button only when the field is populated.

### Recommended YouTube URL formats

Use either:

```text
https://www.youtube.com/watch?v=VIDEO_ID
```

or:

```text
https://youtu.be/VIDEO_ID
```

The project validator accepts YouTube hosts only.

### Admin steps

1. Upload the video to YouTube.
2. Set visibility to **Public** or **Unlisted**.
3. Copy the normal YouTube watch URL.
4. Open Django Admin.
5. Edit the relevant project.
6. Open the **Demo** section.
7. Paste the URL into **YouTube demo URL**.
8. Save the project.
9. Confirm the project is published.
10. Open the public project detail page.
11. Click **Watch demo on YouTube**.

Do not use a private video, because visitors will not be able to watch it. The button opens a privacy-enhanced YouTube iframe inside an in-page modal. The iframe is created only after the visitor clicks the button and is removed when the modal closes.

## 11. Configure enquiry email

The current flow is intentionally separated:

- General enquiry: saves the lead and sends an email.
- Project enquiry: saves the lead and opens WhatsApp.
- Project enquiry does not require email delivery.

The general enquiry email is sent to:

```env
PUBLIC_CONTACT_EMAIL=support@projectvybe.com
```

The sender should be a verified address on the domain:

```env
DEFAULT_FROM_EMAIL=notifications@projectvybe.com
```

The user's email is used as the reply-to address.

### Resend SMTP setup

In Resend:

1. Add `projectvybe.com`.
2. Add the DNS verification records provided by Resend.
3. Wait until the domain is verified.
4. Create an API key.
5. Set the API key as `EMAIL_HOST_PASSWORD` in Render.

Use:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.resend.com
EMAIL_PORT=587
EMAIL_HOST_USER=resend
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
```

Configure SPF, DKIM, and DMARC for the sending domain. Do not create a second conflicting SPF record; merge values into the existing record.

Resend's SMTP settings are documented at [resend.com/docs/send-with-smtp](https://resend.com/docs/send-with-smtp).

### Email test

Submit the general enquiry form and confirm:

- A `Lead` record appears in Django Admin.
- The email arrives at `support@projectvybe.com`.
- Replying to the email addresses the visitor.
- A project enquiry opens WhatsApp and does not send a duplicate enquiry email.

## 12. Test the temporary Render URL

Before connecting the custom domain, test:

```text
https://your-service.onrender.com/
https://your-service.onrender.com/projects/
https://your-service.onrender.com/services/
https://your-service.onrender.com/about/
https://your-service.onrender.com/enquiry/
https://your-service.onrender.com/admin/
https://your-service.onrender.com/health/
https://your-service.onrender.com/sitemap.xml
https://your-service.onrender.com/robots.txt
```

Test:

- Desktop, tablet, and mobile layouts
- Navigation and mobile menu
- Project and service cards
- Cloudinary images
- Project gallery images
- YouTube demo button
- Admin login and content editing
- General enquiry email
- Project WhatsApp flow
- CSRF-protected form submissions
- Static CSS and JavaScript
- 404 and 500 pages

If a form shows a CSRF 403 error, confirm that the exact HTTPS origin exists in `CSRF_TRUSTED_ORIGINS`.

## 13. Attach the custom domain

After the temporary Render URL passes testing:

1. Open the Render web service.
2. Add `projectvybe.com`.
3. Add `www.projectvybe.com`.
4. Configure the DNS records shown by Render.
5. Wait for DNS verification.
6. Confirm the Render TLS certificate is active.

Render automatically provisions TLS certificates and redirects HTTP traffic to HTTPS. See [Render custom domains](https://render.com/docs/custom-domains).

Update Render environment variables:

```env
ALLOWED_HOSTS=your-service.onrender.com,projectvybe.com,www.projectvybe.com

CSRF_TRUSTED_ORIGINS=https://your-service.onrender.com,https://projectvybe.com,https://www.projectvybe.com

SITE_URL=https://projectvybe.com
```

Redeploy after changing these values. `SITE_URL` controls canonical URLs, sitemap URLs, robots references, Open Graph URLs, and generated public links.

## 14. Final production smoke test

Verify:

- `https://projectvybe.com` loads successfully.
- HTTP redirects to HTTPS.
- `www` behaves according to the chosen canonical-domain strategy.
- No browser mixed-content warnings appear.
- Static CSS and JavaScript load correctly.
- Cloudinary images load correctly.
- Neon records are visible in Admin.
- General enquiries arrive by email.
- Project enquiries open the correct WhatsApp number.
- YouTube demo links open correctly.
- Sitemap and robots URLs use the custom domain.
- `DEBUG=False`.
- Admin login works.
- No secrets appear in logs or page source.

## 15. Backups and ongoing maintenance

Maintain:

- Neon backups and restore testing
- Periodic PostgreSQL logical exports
- Cloudinary asset backups
- Git tags for known-good releases
- Render deployment logs
- Resend delivery logs
- A written record of production environment variables, without storing secret values in Git

Before a risky migration:

1. Back up Neon.
2. Deploy the code.
3. Run migrations deliberately.
4. Check `/health/`.
5. Test the main pages and enquiry flows.

For rollback, redeploy the previous known-good Git commit. Avoid reversing destructive migrations without a database recovery plan.

## 16. Final architecture

```text
Visitor
  ↓
projectvybe.com
  ↓
Render Django Web Service
  ├── Neon PostgreSQL
  ├── Cloudinary images
  └── Resend SMTP email
```
