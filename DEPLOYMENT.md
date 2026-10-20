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

The build script runs `collectstatic`. Database migrations run in Render's **Pre-Deploy Command**, which Render executes after a successful build and before it switches traffic to the new version. If the migration fails, the deploy is stopped and the live site keeps running the previous version.

```text
Pre-Deploy Command:
python manage.py migrate --noinput
```

Set it under the service's **Settings → Build & Deploy → Pre-Deploy Command**. Pushing to `main` then rebuilds, migrates and deploys in one step.

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
DEFAULT_FROM_EMAIL=ProjectVybe Enquiries <notifications@projectvybe.com>

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.resend.com
EMAIL_PORT=587
EMAIL_HOST_USER=resend
EMAIL_HOST_PASSWORD=your-resend-api-key
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=10

# Optional Cloudflare Turnstile keys (bot check on forms); leave unset to disable.
# TURNSTILE_SITE_KEY=your-turnstile-site-key
# TURNSTILE_SECRET_KEY=your-turnstile-secret-key

# Private admin path (no leading slash). Choose something hard to guess.
ADMIN_URL=your-private-admin-path/
# Render sits behind one reverse proxy; this makes rate limits use the real visitor IP.
TRUSTED_PROXY_COUNT=1

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
# HSTS: omit SECURE_HSTS_SECONDS to use the production default of 31536000 (1 year).
# Only do this once HTTPS is confirmed on projectvybe.com and www.projectvybe.com,
# because browsers will refuse plain HTTP for the whole year.
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
```

Rules:

- Confirm that `www.projectvybe.com` redirects (301) to `projectvybe.com`.
- `ADMIN_URL` has no leading slash and ends with `/` (added automatically if missing). `/admin/` stops working once it is changed, and robots.txt no longer lists the admin path.
- Keep the Neon **direct** connection string. The app reuses connections (`CONN_MAX_AGE=60`) and reopens any that Neon dropped while idle.

- `ALLOWED_HOSTS` contains hostnames only; do not include `https://`.
- `CSRF_TRUSTED_ORIGINS` contains complete HTTPS origins.
- `SITE_URL` contains the canonical public origin without a trailing slash.
- `DEBUG` must be `False` in production.
- Never expose `SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_URL`, or `EMAIL_HOST_PASSWORD`.

## 7. Run migrations and create the admin user

After the first Render deployment, open the Render Shell and run:

```bash
python manage.py check --deploy
python manage.py createsuperuser
```

(Migrations already ran in the Pre-Deploy Command from section 5.) Open:

```text
https://your-service.onrender.com/<ADMIN_URL>
```

Future deployments that contain migrations need no manual step: the Pre-Deploy Command applies them before the new version goes live. Take a database backup before destructive schema changes.

### Admin sign-in uses two-factor authentication

Admin only lets in staff who have confirmed a one-time-password device. A password alone is not enough.

**First sign-in after this version is deployed** (nobody has a device yet):

1. In the Render Shell run `python manage.py addstatictoken <username>`. It prints a one-time backup code.
2. Open the admin address, enter your username and password, choose the backup device and paste the code. Each backup code works once.
3. In Admin open **Totp devices → Add**, choose your user and save. Open the device and scan the QR code with an authenticator app (Google Authenticator, Microsoft Authenticator, Aegis and similar).
4. Open **Static devices** and create a fresh set of backup codes. Store them offline.
5. From then on sign in with the 6-digit code from the app.

**Lost phone:** use a backup code, or run `addstatictoken` again from the Render Shell, then add a new authenticator device.

**Passwords:** use a unique password of 20 or more characters for the superuser (a password manager helps). The site enforces at least 12 characters. Give day-to-day staff their own accounts with only the permissions they need (for example: Legal pages and Site settings, not Users).

**Lockout:** five failed password attempts from one IP address lock that address out for one hour (the lock is by address, so a stranger cannot lock you out of your own account). The owner gets one email when an IP is locked out and one on every staff sign-in. Failed attempts are only logged. To unlock an address at once, run in the Render Shell:

```bash
python manage.py axes_reset
```

(or `python manage.py axes_reset_ip <ip-address>` for one address). Wrong one-time codes are slowed down by django-otp itself.

### Cloudflare Turnstile (optional bot check on forms)

Turnstile adds a small invisible-or-click check to the enquiry form, the project enquiry window and the privacy request form. It is off until both keys exist.

1. In the Cloudflare dashboard open **Turnstile → Add widget**, add `projectvybe.com` and `www.projectvybe.com`, and copy the site key and secret key.
2. In Render set `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` and redeploy.

If Cloudflare cannot be reached, visitors are let through (the hidden honeypot field and the per-IP rate limits still apply), so an outage never loses an enquiry.

### Site Settings, Legal pages and Privacy requests in Admin

- **Site settings** (one record): contact email and WhatsApp number (blank means the Render values are used), phone, address, business hours, legal name, registered address, GSTIN, grievance officer, footer text, social links, share image, announcement bar, homepage heading and sections, 404 text and maintenance mode. Changes appear within about a minute because each server keeps the settings cached for 60 seconds.
- **Maintenance mode:** tick it to show visitors a 503 page. Signed-in staff, the admin, `/health/`, `robots.txt` and the sitemap keep working. The admin address is always reachable, so you can sign in and switch it off.
- **Legal pages:** edit the draft (Markdown), then tick **Publish this draft as a new version** and save. Visitors see only published versions, every enquiry consent record points to the exact Privacy Policy version shown at that time, and old versions cannot be edited. Placeholders such as `{contact_email}`, `{legal_name}`, `{registered_address}`, `{grievance_officer_name}` and `{grievance_officer_email}` are filled from Site Settings. The three new pages (Grievance Redressal, Shipping & Delivery, Academic Integrity) are drafts of general text: have a lawyer review all policies before relying on them.
- **Privacy requests** (`/privacy/request/`): each request emails the owner and shows matching enquiries in Admin. Check that the person owns the email address, then in **Enquiries** use *Export selected enquiries as CSV* to answer an access request, *Anonymise selected enquiries* to answer a deletion request, or *Mark consent as withdrawn* for a STOP request, and close the request. A WhatsApp STOP message is handled the same way: find the enquiry by reference or email and withdraw consent.

### Scheduled job: delete old enquiries (24 months)

The Privacy Policy promises to remove personal details from enquiries after 24 months. Add a Render **Cron Job** (same repository and environment variables as the web service):

```text
Schedule:  0 3 1 * *          (03:00 on the 1st of each month)
Command:   python manage.py anonymise_old_leads
```

Preview what it would do with `python manage.py anonymise_old_leads --dry-run`. Nothing becomes due until 24 months after the first enquiry, so this can be set up any time before then.

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

- General enquiry: saves the lead, sends an email to ProjectVybe, and sends a confirmation email to the visitor.
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
- A confirmation email arrives at the visitor's submitted email address.
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
https://your-service.onrender.com/<ADMIN_URL>
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

## Phase 3: online payments (Razorpay)

Payments stay OFF until you tick **Payments enabled** in Admin > Site settings.

1. **Pre-Deploy Command** stays `python manage.py migrate --noinput` (new migrations: catalog 0007, core 0003, orders 0001, leads 0008, legal 0003).
2. **Environment variables on Render** (test keys first): `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `ORDERS_FROM_EMAIL` (for example `ProjectVybe Orders <orders@projectvybe.com>`; verify that sender in Resend).
3. **Razorpay dashboard**: turn on auto-capture. Add a webhook at `https://<your-domain>/payments/razorpay/webhook/` with events `payment.captured`, `payment.failed`, `refund.processed`, `refund.failed`, using the same secret as `RAZORPAY_WEBHOOK_SECRET`.
4. **Render Cron Jobs** (same build and env as the web service):
   - `python manage.py send_overdue_alerts` every 15 minutes
   - `python manage.py expire_unpaid_orders` daily
   - `python manage.py anonymise_old_leads` monthly
5. **Policies**: Refund, Shipping, Terms and Privacy have new DRAFT wording. Review it with a lawyer, then press Publish in Admin. Checkout will not open if Terms or Refund Policy has no published version.
6. **Per project**: set a price, tick "Accept online payment". Add-on prices are set on each add-on, or per project in the project's add-on price rows.
7. **Before going live**: take a Neon backup, swap in live keys after KYC, make one real Rs 1-10 payment and refund it, then enable.

## UI redesign, Courses and Blog

- **Migrations to run on deploy** (the Pre-Deploy Command already does this): `courses.0001`, `blog.0001`, `leads.0009`.
- **Fonts** are self-hosted in `static/fonts/` (Bricolage Grotesque, Instrument Sans, JetBrains Mono; SIL Open Font License). Nothing is loaded from Google at runtime.
- **Courses:** add courses in Admin > Courses. Sign-ups appear under Waitlist entries (CSV export and anonymise actions). Add a monthly Render Cron Job: `python manage.py anonymise_old_waitlist` (removes personal details after 24 months, like enquiries).
- **Blog:** create an Author and a Blog category first, then Posts. A post goes live when its status is Published and its publish time has passed, so a future time schedules it. "Open preview" in the post form shows a draft to logged-in staff. The RSS feed is `/blog/feed/` and posts are in `sitemap.xml`.
- **Images in posts:** the Markdown editor accepts only `https://` image links. Upload images to Cloudinary at the size you need (about 1200 px wide) and paste the link. Posts' cover images use the existing 640 and 1200 px sizes.
- **Policies:** the Privacy Policy draft does not yet mention the course waitlist (name, email, phone kept for up to 24 months). Add a line before you publish courses.

## Redesign round 2: FAQs, social icons, add-ons

- **FAQs** are managed in Admin > Core > FAQs. Tick the pages each question appears on (home, project pages, services, contact, courses). Changes show within about five minutes. A few starter questions are added by migration `core.0005`; edit or delete them.
- **Social icons** in the footer come from Admin > Site settings > Brand and social links. The migration fills in placeholder links (instagram.com/projectvybe and similar). **Replace them with your real profiles, or clear a field to hide that icon.** The WhatsApp icon uses your WhatsApp number.
- **Add-ons** on a project page: tick-to-add cards with a live total when online payment is on; plain cards with an "Ask about this" link otherwise. Set add-on prices in Admin > Project addons, or per project in the project's add-on price rows.
- **Testing payments locally:** put your Razorpay TEST keys in `.env` (`RAZORPAY_KEY_ID=rzp_test_...`, `RAZORPAY_KEY_SECRET=...`), tick "Payments enabled" in Site settings, and tick "Accept online payment" on a priced project. Use Razorpay's test cards or UPI (`success@razorpay`). The optional `RAZORPAY_API_BASE` setting exists only to point at a fake gateway while developing; leave it unset on Render.
