# ProjectVybe - Complete AI Project Context

This document is a handoff guide for another AI model, developer, or coding agent. Read it before changing the project.

## 1. Project identity

ProjectVybe is a Django website for publishing and exploring practical technology projects and services.

The public product has three connected goals:

1. Help visitors explore project ideas across technology domains.
2. Help students, developers, and teams find training, mentorship, documentation, presentation, and software support.
3. Convert interest into a structured enquiry, email conversation, or project WhatsApp conversation.

Current brand language:

- Build. Learn. Grow.
- Practical technology projects, training, mentorship, and software services to help you turn ideas into working solutions.
- ProjectVybe brings together practical software projects, AI/ML and computer science project ideas, training, mentorship, documentation support, and software development services in one place.

The project is catalogue-driven. Public content is managed through Django Admin rather than hardcoded in the views.

## 2. Technology stack

- Python
- Django 6.x
- PostgreSQL in production
- SQLite in local development only
- `django-environ` for environment variables
- `psycopg` for PostgreSQL
- Cloudinary for permanent images
- Gunicorn for the production WSGI server
- WhiteNoise for static files
- Vanilla JavaScript
- HTML templates and CSS
- Render is the planned web host
- Neon PostgreSQL is the planned production database
- Resend SMTP is the planned enquiry email provider
- YouTube is used for optional project demonstrations

Dependencies are defined in [requirements.txt](requirements.txt).

## 3. Repository structure

```text
ProjectVybe/
├── manage.py
├── config/
│   ├── settings.py          # Environment-driven Django settings
│   ├── urls.py              # Root URL configuration
│   ├── asgi.py
│   └── wsgi.py
├── catalog/
│   ├── models.py            # Categories, projects, services, reviews
│   ├── admin.py             # Catalogue management interface
│   ├── cloudinary.py        # Upload folders
│   ├── validators.py        # YouTube URL validation
│   ├── migrations/
│   └── tests.py
├── leads/
│   ├── models.py            # Enquiry/Lead model
│   ├── forms.py             # Public enquiry validation
│   ├── views.py             # Email and WhatsApp enquiry flows
│   ├── utils.py             # Message and email generation
│   ├── admin.py
│   ├── migrations/
│   └── tests.py
├── pages/
│   ├── views.py             # Public pages and catalogue queries
│   ├── urls.py
│   ├── sitemaps.py
│   └── tests.py
├── core/
│   ├── views.py             # Health and error pages
│   ├── seo.py               # Canonical URLs and JSON-LD
│   ├── context_processors.py
│   ├── templatetags/
│   └── tests.py
├── templates/
│   ├── base.html
│   ├── components/
│   └── pages/
├── static/
│   ├── css/base.css
│   ├── css/components.css
│   ├── js/site.js
│   └── images/
├── db.sqlite3               # Local development database; not production
├── build.sh                 # Production collectstatic command
├── Procfile                 # Gunicorn process declaration
├── .env.example             # Safe environment-variable template
├── README.md
├── DEPLOYMENT.md
└── PROJECT_CONTEXT.md       # This document
```

Generated `staticfiles/` files are deployment output and should not be manually edited. Source static files live in `static/`.

## 4. Django applications

### `catalog`

Owns public catalogue content:

- `Category`
- `ProjectAddon`
- `Project`
- `ProjectImage`
- `Service`
- `Review`

### `leads`

Owns public enquiries:

- `Lead`
- `LeadForm`
- Email notification generation
- WhatsApp message generation

### `pages`

Owns public page views, catalogue filtering, project detail pages, policy pages, sitemap configuration, and SEO context.

### `core`

Owns the health endpoint, error pages, global public-site context, canonical URL helpers, and category asset template tags.

## 5. Data models

### Category

Fields:

- `name`: category display name
- `slug`: unique URL/filter slug
- `description`: short category explanation
- `image`: Cloudinary identity image, usually square
- `homepage_image`: Cloudinary wide homepage/category-card image
- `is_active`: controls public visibility
- `created_at`

Only active categories appear in navigation, category carousels, and project filtering.

### ProjectAddon

Fields:

- `name`
- `slug`
- `description`
- `is_active`
- `ordering`

Project add-ons are global records assigned to projects through a many-to-many relationship. Examples include documentation, PPT/presentation support, publication support, and 1:1 mentorship.

### Project

Fields:

- `title`
- `slug`
- `short_description`
- `description`
- `usage`
- `features`: one feature per line
- `technology_stack`: one technology per line
- `requirements`
- `thumbnail`: Cloudinary project thumbnail
- `youtube_demo_url`: optional validated YouTube URL
- `category`: required foreign key to `Category`
- `addons`: many-to-many relationship to `ProjectAddon`
- `featured`: controls homepage featured-project display
- `is_published`: controls all public project visibility
- `created_at`
- `updated_at`

Visibility rules:

- A project must be `is_published=True`.
- Its category must also be `is_active=True`.
- A project can be published without being featured.
- A project can be featured only if it should appear in the homepage featured section.

### ProjectImage

Fields:

- `project`: foreign key to `Project`
- `image`: Cloudinary gallery image
- `alt_text`
- `ordering`

Gallery images are displayed on the project detail page in ordering order.

### Service

Fields:

- `name`
- `slug`
- `short_description`
- `description`
- `image`: optional Cloudinary image
- `is_active`
- `ordering`

Only active services appear publicly. Services are company-wide support offerings, while `ProjectAddon` records are project-specific options.

### Review

Fields:

- `reviewer_name`
- `reviewer_role`
- `message`
- `is_published`
- `ordering`
- `created_at`

Only published reviews appear on the homepage. Reviews are displayed in an accessible carousel.

### Lead

Fields:

- `project`: optional foreign key to a project
- `name`
- `email`
- `phone`
- `selected_services`: many-to-many services
- `selected_addons`: many-to-many project add-ons
- `message`
- `status`: `new`, `contacted`, `in_progress`, `completed`, or `closed`
- `created_at`

Lead records are private business data and should not be exported with public catalogue fixtures unless intentionally required.

## 6. Public routes

Root routes are defined in [config/urls.py](config/urls.py), [pages/urls.py](pages/urls.py), and [leads/urls.py](leads/urls.py).

| URL | Name | Purpose |
|---|---|---|
| `/` | `pages:home` | Homepage |
| `/projects/` | `pages:project_catalogue` | Published project catalogue |
| `/projects/search/` | `pages:project_search` | JSON live-search endpoint for published projects |
| `/projects/<slug>/` | `pages:project_detail` | Published project detail |
| `/services/` | `pages:services` | Active services |
| `/about/` | `pages:about` | About page and active categories |
| `/enquiry/` | `leads:enquiry` | General enquiry and project enquiry endpoint |
| `/enquiry/success/` | `leads:success` | Legacy/session-based success route |
| `/health/` | `core:health` | JSON health check |
| `/sitemap.xml` | Django sitemap | SEO sitemap |
| `/robots.txt` | `pages:robots_txt` | Crawler instructions |
| `/privacy/` | `pages:privacy_policy` | Privacy policy |
| `/terms/` | `pages:terms` | Terms and conditions |
| `/refund-policy/` | `pages:refund_policy` | Refund/cancellation policy |
| `/cookies/` | `pages:cookies` | Cookie policy |
| `/admin/` | Django Admin | Private content and lead management |

## 7. Page behavior

### Homepage

`pages.views.home` loads:

- Up to 3 newest published featured projects
- Up to 6 active services
- All published reviews
- Active categories through the global context processor

Homepage sections include:

- Hero and brand message
- What ProjectVybe offers
- Explore by area/category carousel
- Featured projects
- Services carousel
- How it works
- Why ProjectVybe
- Reviews carousel
- Final contact CTA

Category, service, and review carousels use the same JavaScript carousel system and expose arrows, counts, dots, keyboard focus, and smooth scrolling.

### Projects catalogue

The catalogue:

- Shows only published projects from active categories.
- Supports text search through title, short description, description, technology stack, and features.
- Supports category filtering.
- Paginates at 9 projects per page.
- Uses `noindex, follow` for filtered search/category URLs.
- Includes published projects in the sitemap.

### Project detail

The detail page displays:

- Breadcrumbs
- Category badge
- Project thumbnail
- Optional gallery
- `Get this project` enquiry button
- Optional YouTube demo button
- Description
- Key features
- Technology stack
- Usage and use case
- Requirements
- Project add-ons
- FAQ content
- Up to 3 related projects
- Final project enquiry CTA

Related projects first use projects in the same category. If fewer than 3 exist, the view fills the remaining slots with other published projects.

### Services page

The services page displays all active services ordered by `ordering`, then `name`. Each service has an enquiry link that preselects the service in the general enquiry form.

### About page

The About page contains:

- ProjectVybe purpose and audience
- Build, Learn, and Grow support cards
- Audience/support groups
- Active technology category carousel
- Final CTA

Categories are loaded dynamically from active `Category` records.

## 8. Enquiry workflows

There are two intentionally different enquiry workflows.

### General enquiry: email workflow

Used for:

- Contact page
- General service enquiry
- Service-page enquiry links
- General project/service discussion without the project modal

Flow:

1. Visitor submits `/enquiry/`.
2. `LeadForm` validates the request.
3. A `Lead` record is saved.
4. `send_enquiry_email()` sends an email to `PUBLIC_CONTACT_EMAIL`.
5. The visitor sees a confirmation state.

Email settings:

- `PUBLIC_CONTACT_EMAIL`: recipient
- `DEFAULT_FROM_EMAIL`: sender
- User email: reply-to address
- `EMAIL_*`: SMTP configuration

### Project enquiry: WhatsApp workflow

Used by the project detail `Get this project` button.

The modal has two steps:

1. Visitor information: name, email, phone.
2. Project support: add-ons and message.

The form includes:

- CSRF token
- Honeypot field named `website`
- Project ID
- Hidden `project_wizard=1`

Flow:

1. Visitor opens the project modal.
2. JavaScript validates Step 1 before showing Step 2.
3. The form is submitted to `/enquiry/`.
4. The lead is saved.
5. The enquiry text is URL-encoded into a WhatsApp URL.
6. The visitor is redirected to `https://wa.me/<number>?text=...`.

The WhatsApp number is taken from `WHATSAPP_NUMBER`. Non-digit characters are removed before building the `wa.me` URL.

Project enquiries do not need to send a duplicate email.

### WhatsApp message format

The generated message is built by `leads.utils.build_enquiry_message()` and contains:

```text
Hello ProjectVybe,

I am interested in the [Project title] project.

Name: [name]
Email: [email]
Phone: [phone]

Additional services:
[selected services and add-ons]

Message: [visitor message]
```

## 9. Form validation rules

`LeadForm` rules:

- Name and email are required through the model/form.
- Phone is optional for general enquiries.
- Phone is required for project enquiries.
- Phone accepts digits, spaces, `+`, parentheses, periods, and hyphens.
- Phone must contain at least 7 digits.
- Message must contain at least 10 characters.
- Project choices include only published projects from active categories.
- Service choices include only active services.
- Add-on choices include only active add-ons assigned to the selected project.
- A filled honeypot rejects the submission.

## 10. Admin behavior

Admin is the primary content-management interface.

### Category Admin

Manage:

- Name, slug, description, active state
- Identity image
- Homepage image

### Project Admin

Manage:

- Basic information
- Content fields
- Thumbnail
- YouTube demo URL
- Project add-ons
- Featured/published flags
- Ordered gallery images through an inline

Actions include publishing, unpublishing, featuring, and removing featured status.

### Service Admin

Manage active service records and ordering.

### Review Admin

Manage reviewer details, publication state, and ordering.

### Lead Admin

Manage private enquiries, search by contact information, and update status as the conversation progresses.

## 11. Image system

All model-backed catalogue images should use Cloudinary. Do not use Render's local filesystem for permanent media.

Cloudinary folders are defined in [catalog/cloudinary.py](catalog/cloudinary.py):

- Categories: `projectvybe/categories/`
- Project thumbnails: `projectvybe/projects/<project-slug>/`
- Project gallery: `projectvybe/projects/<project-slug>/` (the current code uses the same project folder)
- Services: `projectvybe/services/`

Recommended source sizes:

| Asset | Recommended size | Ratio |
|---|---:|---:|
| Category identity image | `512 x 512` | 1:1 |
| Category homepage image | `1600 x 1000` | 16:10 |
| Project thumbnail | `1600 x 1000` | 16:10 |
| Project gallery image | `1600 x 1200` | 4:3 |
| Service image | `1600 x 900` | 16:9 |

The CSS uses `object-fit: cover`, so consistent ratios prevent unexpected cropping. The view layer applies Cloudinary transformations such as width limits, automatic quality, and automatic format delivery when possible.

## 12. YouTube demo behavior

`catalog.validators.validate_youtube_url` accepts YouTube hosts:

- `youtube.com`
- `www.youtube.com`
- `youtu.be`
- `www.youtu.be`

Recommended values:

```text
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
```

Admin workflow:

1. Upload the demo to YouTube.
2. Make it Public or Unlisted.
3. Copy the normal watch URL.
4. Paste it into Project Admin under Demo > YouTube demo URL.
5. Save and publish the project.

The project detail template conditionally renders a `Watch demo on YouTube` button. It opens a privacy-enhanced `youtube-nocookie.com` iframe inside an in-page modal. The video iframe is loaded only after the visitor clicks the button, and its source is removed when the modal closes. The modal also supports backdrop closing and the Escape key.

## 13. Frontend architecture

### Template inheritance

All pages extend [templates/base.html](templates/base.html).

The base template provides:

- HTML document shell
- Meta description
- Robots directive
- Canonical URL
- Open Graph metadata
- Twitter metadata
- Static CSS loading
- Navbar
- Messages
- Main content block
- Footer
- Deferred JavaScript
- Optional JSON-LD

### Reusable components

Reusable components are in `templates/components/`:

- Navbar
- Footer
- Breadcrumbs
- Buttons
- Messages
- Form fields
- Project enquiry modal
- Category cards
- Project cards
- Service cards
- Add-on cards

### CSS

Main styles:

- [static/css/base.css](static/css/base.css): variables, reset, layout foundations, typography
- [static/css/components.css](static/css/components.css): cards, buttons, grids, carousels, page-specific components, responsive rules

The UI uses a dark navy, cobalt blue, pale blue, white, and muted surface palette. Cards use rounded corners, subtle borders, shadows, and smooth hover transforms. Preserve the existing design tokens before adding one-off styles.

### JavaScript

[static/js/site.js](static/js/site.js) contains four main behaviors:

1. Mobile navigation and Projects dropdown.
2. Two-step project enquiry wizard.
3. Project enquiry modal open/close behavior.
4. Category, service, and review carousels.
5. Live project search modal with debounced JSON requests.

Carousel selectors:

- `data-category-carousel`
- `data-service-carousel`
- `data-review-carousel`

Carousel behavior includes:

- Previous/next controls
- Smooth scrolling
- Dynamic slide count
- Current/total counter
- Dots
- Disabled controls at the ends
- Resize recalculation
- Keyboard-focusable viewport

The project search is available from the navbar on the project catalogue and project detail pages. Typing opens a themed search modal, queries the JSON search endpoint after a short debounce, and renders up to eight published matching projects with their category, description, technologies, thumbnail, and detail link. Only projects in active categories are returned.

## 14. SEO behavior

SEO helpers are in [core/seo.py](core/seo.py).

The application uses configured `SITE_URL` instead of trusting the request Host header when generating:

- Canonical URLs
- Sitemap URLs
- Open Graph URLs
- JSON-LD URLs
- Robots sitemap reference

Static routes and published project details are included in the sitemap. Filtered project searches are marked `noindex, follow`.

## 15. Settings and environment variables

Settings are loaded from `.env` locally and from the hosting provider in production.

Required production variables:

```env
SECRET_KEY=...
DEBUG=False
DATABASE_URL=...
ALLOWED_HOSTS=...
CSRF_TRUSTED_ORIGINS=...
SITE_URL=https://...
CLOUDINARY_URL=...
```

Communication variables:

```env
WHATSAPP_NUMBER=...
PUBLIC_CONTACT_EMAIL=...
DEFAULT_FROM_EMAIL=...
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=...
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=10
```

Security behavior when `DEBUG=False`:

- PostgreSQL is mandatory.
- `ALLOWED_HOSTS` must be explicit.
- `CSRF_TRUSTED_ORIGINS` must contain valid HTTPS origins.
- HTTPS redirect must be enabled.
- Session cookies must be secure.
- CSRF cookies must be secure.
- Forwarded HTTPS is trusted through the configured proxy header.

## 16. Production deployment summary

The complete deployment guide is in [DEPLOYMENT.md](DEPLOYMENT.md).

Target architecture:

```text
Visitor
  |
  v
Custom HTTPS domain
  |
  v
Render Django Web Service
  |-- Neon PostgreSQL
  |-- Cloudinary images
  `-- Resend SMTP email
```

Main deployment sequence:

1. Run local tests and checks.
2. Create Neon production database.
3. Create Render Web Service.
4. Add production environment variables.
5. Deploy with Gunicorn.
6. Run Django migrations.
7. Create a production superuser.
8. Import or recreate catalogue data.
9. Configure Cloudinary and upload images.
10. Configure Resend and verify email delivery.
11. Test the temporary Render URL.
12. Attach the custom domain.
13. Update `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `SITE_URL`.
14. Run final smoke tests.

## 17. Testing commands

Local development:

```powershell
python manage.py migrate
python manage.py runserver
```

Checks:

```powershell
python manage.py check
python manage.py check --deploy
python manage.py test
```

Production shell:

```bash
python manage.py migrate --noinput
python manage.py check --deploy
python manage.py createsuperuser
```

## 18. Important rules for future AI changes

Before changing code:

1. Read this document and the relevant source files.
2. Check the current Git/worktree state.
3. Preserve unrelated user changes.
4. Determine whether the request is content, styling, behavior, data, or deployment work.
5. Prefer existing components, design tokens, and model-driven content.
6. Add or update tests for behavior changes.
7. Run the relevant Django checks and tests.

Do not:

- Put production secrets in the repository.
- Use SQLite in production.
- Store permanent uploaded media on the Render filesystem.
- Delete catalogue records to solve a display issue without explicit approval.
- Export private leads as public catalogue fixtures.
- Change model fields without creating migrations.
- Replace admin-driven content with hardcoded content unless explicitly requested.
- Remove CSRF tokens from forms.
- Trust the request Host header for canonical URLs.
- Add analytics or tracking cookies without updating privacy/cookie documentation.
- Add payment behavior; payments and public pricing are not currently implemented.

## 19. Known implementation details to verify before modifying

- Homepage featured projects are limited to three records in `pages.views.home`.
- Homepage services are limited to six records.
- The full project catalogue is paginated at nine projects per page.
- Related project cards are limited to three.
- Project detail add-ons are limited to active add-ons assigned to that project.
- Project enquiry phone is required; general enquiry phone is optional.
- General enquiries are email-oriented; project wizard enquiries are WhatsApp-oriented.
- Cloudinary image URLs are safely transformed at render time when supported.
- The local database file `db.sqlite3` contains development data and must not be treated as a production backup.
- The current deployment plan assumes Render + Neon, but the Django application can be hosted elsewhere if the same environment variables and commands are supported.
