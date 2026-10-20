import html
import re

import markdown
import nh3


ALLOWED_TAGS = {
    "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "em", "a", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td", "hr", "br",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}

PLACEHOLDER_PATTERN = re.compile(
    r"\{(contact_email|legal_name|registered_address|grievance_officer_name|"
    r"grievance_officer_email|whatsapp_number)\}"
)


def clean_html(raw_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, **options):
    """Sanitise HTML with an allowlist. Shared by the policy pages and the blog."""
    return nh3.clean(
        raw_html,
        tags=tags,
        attributes=attributes,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
        **options,
    )


def render_markdown(text):
    """Markdown to sanitised HTML. Scripts, event handlers and unsafe links are removed."""
    raw_html = markdown.markdown(text or "", extensions=["extra", "sane_lists"])
    return clean_html(raw_html)


def placeholder_values():
    """Current values for the {placeholders}, with sensible fallbacks."""
    from core.site import contact_email, get_site_settings, whatsapp_number

    site_settings = get_site_settings()
    support = contact_email()
    return {
        "contact_email": support,
        "legal_name": site_settings.legal_name.strip() or "ProjectVybe",
        "registered_address": site_settings.registered_address.strip(),
        "grievance_officer_name": site_settings.grievance_officer_name.strip(),
        "grievance_officer_email": site_settings.grievance_officer_email.strip() or support,
        "whatsapp_number": whatsapp_number(),
    }


def fill_placeholders(html_text, values=None):
    """Swap {placeholders} for Site Settings values, HTML-escaped so they cannot inject markup."""
    values = values if values is not None else placeholder_values()
    # A list item that depends on a detail you have not entered yet (for example the
    # address) is left out instead of showing an empty label.
    for name, value in values.items():
        if not value:
            html_text = re.sub(
                r"<li>(?:(?!</li>).)*\{" + name + r"\}(?:(?!</li>).)*</li>\s*",
                "",
                html_text,
                flags=re.S,
            )
    return PLACEHOLDER_PATTERN.sub(
        lambda match: html.escape(values.get(match.group(1), ""), quote=True),
        html_text,
    )
