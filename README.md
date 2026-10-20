# ProjectVybe

ProjectVybe is a Django website foundation for publishing technology projects and services through Django Admin.

## Current implementation

Phase 1 through Phase 17 provide:

- Django project configuration
- Environment-based settings
- SQLite development support
- PostgreSQL support through `DATABASE_URL`
- WhiteNoise static-file configuration
- Cloudinary-backed model fields for permanent website image storage
- Cloudinary upload folders and secure delivery configuration
- Small, measured query and image-delivery performance optimizations
- Professional Django Admin catalogue management
- Core, catalogue, lead, and page applications
- Category, Project, ProjectImage, Service, and Lead models
- Initial migrations and automated tests
- Reusable responsive frontend design system
- Published project catalogue and project detail pages
- Database-driven Services and About supporting pages
- Public Privacy, Terms, Refund/Cancellation, and Cookie policy pages
- Configured-origin SEO metadata, sitemap, robots.txt, and truthful JSON-LD
- Public enquiry form with project/service validation and Django Admin lead capture
- POST/Redirect/GET confirmation flow with optional WhatsApp continuation
- Deployment-readiness build/start configuration and production documentation

Payments and public pricing are intentionally not implemented.

The repository does not currently contain an approved logo image or favicon. The frontend therefore uses the textual `ProjectVybe` wordmark and does not invent a replacement logo asset. Add approved brand assets in a later phase when they are available.

## Local setup

Use Python 3.13 or another supported Python version.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `.env` with a unique local `SECRET_KEY`. The `.env` file is ignored by Git and must never be committed.

Run migrations and create an admin user:

```powershell
python manage.py migrate
python manage.py createsuperuser
```

Start the development server:

```powershell
python manage.py runserver
```

Open:

- Home: `http://127.0.0.1:8000/`
- Project catalogue: `http://127.0.0.1:8000/projects/`
- Services: `http://127.0.0.1:8000/services/`
- About: `http://127.0.0.1:8000/about/`
- Privacy Policy: `http://127.0.0.1:8000/privacy/`
- Terms & Conditions: `http://127.0.0.1:8000/terms/`
- Refund / Cancellation Policy: `http://127.0.0.1:8000/refund-policy/`
- Cookie Policy: `http://127.0.0.1:8000/cookies/`
- Sitemap: `http://127.0.0.1:8000/sitemap.xml`
- Robots: `http://127.0.0.1:8000/robots.txt`
- Enquiry form: `http://127.0.0.1:8000/enquiry/`
- Health: `http://127.0.0.1:8000/health/`
- Admin: `http://127.0.0.1:8000/admin/`

## Checks and tests

```powershell
python manage.py check
python manage.py test
```

For deployment checks, set production-like environment values and run:

```powershell
python manage.py check --deploy
```

## Environment variables

`.env.example` documents the supported settings. Production values must be supplied by the hosting provider, including `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL`, `WHATSAPP_NUMBER`, and `CLOUDINARY_URL`.

Permanent project and service images will use Cloudinary. Render's local filesystem must not be used for permanent uploads. YouTube URLs are used for project demonstrations. Private source-code archives, documents, and PPT files require a separate protected storage workflow and are not implemented in this phase.

### Enquiries and WhatsApp

The public enquiry form at `/enquiry/` validates published projects and active services before saving a `Lead` with the default `New` status. Submitted leads are managed through Django Admin. After a successful submission, the visitor can continue to WhatsApp when `WHATSAPP_NUMBER` is configured; the form and lead save remain usable without WhatsApp configuration.

### Company services and project add-ons

The `Service` catalogue represents company-wide services shown on the homepage and Services page. Project-specific options are stored separately as `ProjectAddon` records and assigned to individual projects through Django Admin. Current add-on examples include documentation, presentation/PPT support, publication support, and 1:1 mentorship. Add-on selections are saved with enquiries for follow-up; checkout, payments, and public pricing are intentionally not implemented.

### Legal and policy pages

The public policy pages describe the current enquiry-led website model, including the information collected through enquiries, the absence of online payments, and necessary Django cookies used for sessions and CSRF protection. The current implementation does not include analytics, advertising tracking, or a cookie-consent framework. These pages are practical website content and should receive professional legal review before production use.

### SEO and public URL configuration

The application generates canonical URLs, Open Graph URLs, sitemap locations, and the robots sitemap reference from `SITE_URL`. Configure it as the public origin without relying on the request Host header, for example `http://localhost:8000` locally or the production origin supplied by the deployment environment. Trailing slashes and configured path fragments are normalized so generated URLs do not contain duplicate slashes. Search and category-filter variants of the project catalogue are marked `noindex, follow`, while published project detail pages are included in the sitemap.

### Production security configuration

Production must run with `DEBUG=False` and explicit values for `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and an HTTPS `SITE_URL`. When `DEBUG=False`, startup rejects missing or invalid `DATABASE_URL` values instead of falling back to SQLite; SQLite remains available only for local development. Production also requires HTTPS redirect handling and secure session/CSRF cookies. `SECURE_PROXY_SSL_HEADER` is enabled for the planned trusted Render/Cloudflare proxy path, while local development does not trust forwarded HTTPS headers.

HSTS is environment-controlled and preload remains disabled by default. Confirm the final HTTPS domain and subdomain strategy before enabling HSTS preload during deployment. No CSP was added in this phase because the current Cloudinary, static-file, and JSON-LD resource policy requires deployment-level browser verification before introducing a restrictive policy.

### Performance and optimization

The current V1 keeps WhiteNoise compressed static delivery, deferred Vanilla JavaScript, native lazy loading, and CSS aspect-ratio containers. Phase 15 adds focused query-count regression coverage, avoids an unnecessary category lookup for unfiltered catalogue requests, reduces unused relation loading in sitemap generation, and adds `decoding="async"` to non-blocking image markup. Cloudinary transformations are applied only at render time using conservative `f_auto`, `q_auto`, and width-limited `crop=limit` delivery options; stored asset references, upload folders, and database values are unchanged. If Cloudinary transformation support is unavailable, the original delivery URL is used. No cache backend, Redis, Celery, search service, or database migration was added.

### Phase 16 QA notes

The automated suite covers public routes, catalogue filtering and pagination, enquiry validation and CSRF protection, admin access/search smoke tests, SEO output, Cloudinary delivery fallbacks, security configuration, migrations, and generic error pages. The final local checks passed with 93 tests.

These items remain manual QA because they require an actual browser, configured Cloudinary account, or production infrastructure:

- Test the mobile menu with keyboard navigation, Escape, focus visibility, JavaScript disabled, and narrow mobile/tablet/desktop viewports.
- Review long titles, technology tags, descriptions, forms, cards, galleries, and pagination for overflow at representative viewport sizes.
- Verify real Cloudinary uploads and transformed delivery using non-production assets without changing existing asset references or upload folders.
- Verify trusted proxy HTTPS behavior, secure cookies, PostgreSQL connectivity, final host configuration, and HSTS decisions in the real production environment.

### Cloudinary image uploads

Create a Cloudinary account and set `CLOUDINARY_URL` locally or in the deployment environment using the placeholder format shown in `.env.example`. Never commit the real URL because it contains the API key and API secret.

The following Django model fields upload through Cloudinary when saved with a file in Django Admin:

- `Category.image` → `projectvybe/categories/`
- `Project.thumbnail` → `projectvybe/projects/<project-slug>/`
- `ProjectImage.image` → `projectvybe/projects/<project-slug>/`
- `Service.image` → `projectvybe/services/`

The database stores Cloudinary asset references, not image binaries. Cloudinary secure delivery is enabled through Django settings. Without valid Cloudinary credentials, records without images can still be used locally, but an image upload will fail clearly rather than silently writing to the Render filesystem.

## Phase 17 deployment readiness

The repository is prepared for a future Render deployment without performing deployment. The intended application arrangement is a Render Web Service using PostgreSQL supplied through `DATABASE_URL`, Gunicorn, WhiteNoise, and Cloudinary for permanent images. No Render service, Neon database, Cloudflare configuration, production email, or domain connection has been created.

### Build and start commands

The repository uses one small build script and one application-server declaration:

- Build command: `bash build.sh`
- Start command: `gunicorn config.wsgi:application`
- Health-check path: `/health/`

`build.sh` installs the dependencies from `requirements.txt` and runs `collectstatic --noinput`. Database migrations are intentionally a separate controlled step and must not run automatically during the build:

```powershell
python manage.py migrate --noinput
```

The `Procfile` declares the Gunicorn start command. No Dockerfile or `render.yaml` is required by the current simple deployment shape.

### Local versus production

Local development remains independent of Render, Neon, Cloudflare, production email, and the public domain:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

Local development uses `DEBUG=True`, SQLite, and `SITE_URL=http://localhost:8000`. Production must use `DEBUG=False`, PostgreSQL, HTTPS, and explicitly supplied environment variables. The local `.env` file is ignored and must never be committed.

### Production environment checklist

Configure these through the future hosting provider; do not place real values in source control:

- `SECRET_KEY` — long, unique production secret
- `DEBUG=False`
- `DATABASE_URL` — PostgreSQL/Neon connection string
- `ALLOWED_HOSTS` — explicit production hostnames
- `CSRF_TRUSTED_ORIGINS` — explicit HTTPS origins
- `SITE_URL` — canonical HTTPS public origin
- `WHATSAPP_NUMBER` — optional enquiry destination
- `CLOUDINARY_URL` — Cloudinary credential URL
- `PUBLIC_CONTACT_EMAIL` and `DEFAULT_FROM_EMAIL` — optional email configuration values
- HTTPS and HSTS settings documented in `.env.example`

Production startup rejects missing or invalid database configuration and never falls back to SQLite. PostgreSQL migrations should be run deliberately after the application build and before the application is restarted.

### Static files and media

WhiteNoise serves collected static files using the configured compressed manifest storage in production. Run `collectstatic --noinput` during the build. Permanent project, category, gallery, and service images remain in Cloudinary; Render's local filesystem must not be used for permanent media. Cloudinary references, upload folders, and render-time transformations must remain unchanged.

### Future domain and Cloudflare setup

The eventual canonical domain plan is `https://projectvybe.com`, with `projectvybe.in` potentially redirecting to it. This is documentation only. DNS, redirects, certificates, Cloudflare proxying, caching, and HSTS subdomain/preload decisions must be verified after the real domain is connected. They are not configured by this repository phase.

### Backup, recovery, and rollback

- Use Neon/PostgreSQL provider backups and periodic logical exports where appropriate.
- Treat Cloudinary as the source of permanent image assets; do not rely on Render storage for media recovery.
- Keep the private source repository and a previous known-good commit.
- For rollback, redeploy the previous known-good commit, verify migrations and smoke-test routes, and avoid destructive schema changes.

### Future deployment checklist

Before deployment, verify tests, clean migrations, generated production secrets, PostgreSQL, hosts, CSRF origins, HTTPS `SITE_URL`, Cloudinary, WhatsApp, and any required email values.

After deployment, smoke-test the homepage, catalogue, detail pages, services, legal pages, enquiry workflow, admin, static files, Cloudinary uploads, sitemap, robots, 404/500 handling, mobile behavior, SEO metadata, HTTPS, and security headers. Confirm the final domain redirect and HSTS strategy separately.

No production smoke tests are performed during Phase 17.
