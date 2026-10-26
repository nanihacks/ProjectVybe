"""Inline SVG icons, one stroke style, usable as {% icon "mail" %} or {% icon "check" size=18 %}."""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe


register = template.Library()

# Stroke icons on a 24 x 24 grid.
STROKE = {
    "arrow-up-right": "M7 17 17 7M8 7h9v9",
    "check": "m5 12.5 4.5 4.5L19 7.5",
    "check-circle": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM8 12.3l2.6 2.6L16 9.5",
    "plus": "M12 5v14M5 12h14",
    "minus": "M5 12h14",
    "mail": "M3.5 6.5h17v11h-17zM4 7l8 6 8-6",
    "phone": "M6.5 3.5h3l1.5 4-2 1.5a11 11 0 0 0 5 5l1.5-2 4 1.5v3a2 2 0 0 1-2 2A15.5 15.5 0 0 1 4.5 5.5a2 2 0 0 1 2-2Z",
    "map-pin": "M12 21s6.5-5.6 6.5-10.5a6.5 6.5 0 1 0-13 0C5.5 15.4 12 21 12 21ZM12 12.5a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4Z",
    "clock": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3 2",
    "code": "m8 8-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14",
    "book": "M5 4.5h10a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3V4.5ZM5 17a3 3 0 0 1 3-3h10",
    "trend": "M4 17.5 10 11.5l3.5 3.5L20 8.5M15 8.5h5v5",
    "shield": "M12 3.5 5 6v5.5c0 4.2 2.9 7.4 7 9 4.1-1.6 7-4.8 7-9V6l-7-2.5ZM9 12l2.2 2.2L15.5 10",
    "layers": "m12 4 8.5 4.5L12 13 3.5 8.5 12 4ZM3.5 12.5 12 17l8.5-4.5M3.5 16.5 12 21l8.5-4.5",
    "users": "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM2.5 20c.4-3.3 3-5.5 6.5-5.5s6.1 2.2 6.5 5.5M16.5 4.5a3.5 3.5 0 0 1 0 6.8M18 14.7c1.9.7 3.2 2.5 3.5 5.3",
    "file-text": "M7 3.5h7.5L19 8v12.5H7V3.5ZM14 3.5V8.5h5M9.5 12.5h6M9.5 16h6",
    "video": "M3.5 6.5h11a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 2 16V8a1.5 1.5 0 0 1 1.5-1.5ZM16 10.5l5.5-3v9l-5.5-3",
    "spark": "M12 3.5 13.9 10l6.6 2-6.6 2-1.9 6.5-1.9-6.5-6.6-2 6.6-2L12 3.5Z",
    "cpu": "M7 7h10v10H7zM10 10h4v4h-4zM9.5 3.5v3.5M14.5 3.5v3.5M9.5 17v3.5M14.5 17v3.5M3.5 9.5H7M3.5 14.5H7M17 9.5h3.5M17 14.5h3.5",
    "lock": "M6.5 11h11v8.5h-11zM8.5 11V8a3.5 3.5 0 0 1 7 0v3",
    "phone-mobile": "M8 3.5h8a1.5 1.5 0 0 1 1.5 1.5v14a1.5 1.5 0 0 1-1.5 1.5H8A1.5 1.5 0 0 1 6.5 19V5A1.5 1.5 0 0 1 8 3.5ZM10.5 18h3",
    "globe": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM3.5 12h17M12 3.5c2.5 2.6 3.7 5.4 3.7 8.5s-1.2 5.9-3.7 8.5c-2.5-2.6-3.7-5.4-3.7-8.5S9.5 6.1 12 3.5Z",
    "database": "M12 10c4.4 0 8-1.3 8-3s-3.6-3-8-3-8 1.3-8 3 3.6 3 8 3ZM4 7v5c0 1.7 3.6 3 8 3s8-1.3 8-3V7M4 12v5c0 1.7 3.6 3 8 3s8-1.3 8-3v-5",
    "message": "M4 5.5h16v10.5H10l-4.5 3.5V16H4V5.5Z",
    "menu": "M4 7h16M4 12h16M4 17h16",
    "chevron-down": "m6 9 6 6 6-6",
    "search": "M10.8 17.6a6.8 6.8 0 1 0 0-13.6 6.8 6.8 0 0 0 0 13.6ZM16 16l5 5",
    "download": "M12 4v11M7.5 11 12 15.5 16.5 11M5 19.5h14",
    "presentation": "M3.5 4.5h17v11h-17zM12 15.5v4M8 19.5h8M7.5 12l3-3 2.5 2 3.5-4",
    "book-open": "M12 6.5C10.5 5 8 4.5 4.5 4.5V18c3.5 0 6 .5 7.5 2 1.5-1.5 4-2 7.5-2V4.5C16 4.5 13.5 5 12 6.5ZM12 6.5V20",
    "award": "M12 14a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11ZM8.5 13.2 7.5 21l4.5-2.5 4.5 2.5-1-7.8",
    "rocket": "M14 4.5c3 0 5.5 2.5 5.5 5.5-1.5 4-4.5 6.5-8 7.5l-4.5-4.5C8 9.5 10.5 6 14 4.5ZM9 17.5l-3 .5.5-3M15 9.5h.01",
    "wrench": "M14.5 6.5a4 4 0 0 0 4.8 4.8l-9.5 9.5a2.1 2.1 0 0 1-3-3l9.5-9.5a4 4 0 0 0-1.8-1.8Z",
    "chart": "M4.5 19.5V5M4.5 19.5h15M8.5 16v-4M12.5 16V8.5M16.5 16v-6",
}

# Which icon an add-on shows, picked from its name so each extra looks different.
ADDON_ICONS = (
    (("document", "report", "readme", "write"), "file-text"),
    (("present", "slide", "ppt", "viva", "demo"), "presentation"),
    (("publication", "paper", "research", "journal", "thesis"), "book-open"),
    (("mentor", "guidance", "1:1", "coach", "training", "session", "call"), "users"),
    (("code", "source", "explain", "review"), "code"),
    (("video", "record", "walkthrough"), "video"),
    (("deploy", "hosting", "install", "setup", "set up", "configur"), "rocket"),
    (("support", "bug", "fix", "maintenance", "customi"), "wrench"),
    (("certificate", "award"), "award"),
    (("analytic", "report card", "dashboard", "data"), "chart"),
    (("security", "secure"), "shield"),
)

# Filled brand glyphs (simplified shapes).
FILLED = {
    # Solid block arrows, drawn symmetrically about the centre of the 24 grid so they sit centred in buttons.
    "arrow-right": "M4.5 10.9h7.6V6.4l7.4 5.6-7.4 5.6v-4.5H4.5z",
    "arrow-left": "M19.5 10.9h-7.6V6.4L4.5 12l7.4 5.6v-4.5h7.6z",
    "arrow-up": "M10.9 19.5v-7.6H6.4L12 4.5l5.6 7.4h-4.5v7.6z",
    "linkedin": "M4 9h4v11H4zM6 3.8a2.2 2.2 0 1 1 0 4.4 2.2 2.2 0 0 1 0-4.4ZM10.2 9h3.8v1.6c.6-1.1 1.9-1.9 3.7-1.9 3.3 0 4.3 2.1 4.3 5.1V20h-4v-5.5c0-1.4-.4-2.4-1.8-2.4s-2 1-2 2.5V20h-4z",
    "x": "M4 4h4.2l4.3 5.8L17.6 4H20l-6.4 7.4L20.5 20h-4.2l-4.7-6.3L6.2 20H3.8l7-8.1z",
    "quote": "M4 13.5C4 9.4 6.3 6.3 10 5l.8 1.6C8.9 7.6 8 9 8 10.5h2.8V17H4zM13.2 13.5c0-4.1 2.3-7.2 6-8.5l.8 1.6c-1.9 1-2.8 2.4-2.8 3.9H20V17h-6.8z",
}

# Brand glyphs drawn as strokes.
BRAND_STROKE = {
    "instagram": "M7.5 3.5h9a4 4 0 0 1 4 4v9a4 4 0 0 1-4 4h-9a4 4 0 0 1-4-4v-9a4 4 0 0 1 4-4ZM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM17.2 6.8h.01",
    "youtube": "M5.5 5.5h13a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3h-13a3 3 0 0 1-3-3v-7a3 3 0 0 1 3-3ZM10 9l5 3-5 3z",
    "github": "M9 19c-4 1.5-4-2-6-2m12 4v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21",
    "facebook": "M17.5 3.5h-2.7a4.3 4.3 0 0 0-4.3 4.3v2.7H7.5v3.8h3V21h3.9v-6.7h2.9l.7-3.8h-3.6V8a.9.9 0 0 1 .9-.9h2.2z",
    "whatsapp": "M3.5 20.5 5 16A8.5 8.5 0 1 1 8.2 19L3.5 20.5ZM9.2 8.8c-.3.8-.2 1.8.6 3.1s1.9 2.2 3.1 2.7c.8.3 1.5.1 1.9-.5l.4-.7-1.9-1-.7.7a3.7 3.7 0 0 1-1.8-1.8l.7-.7-.9-2z",
}


@register.filter
def addon_icon(name):
    """The icon name for an add-on, chosen from words in its title."""
    lowered = str(name or "").lower()
    for words, icon_name in ADDON_ICONS:
        if any(word in lowered for word in words):
            return icon_name
    return "layers"


@register.simple_tag
def icon(name, size=20, css_class=""):
    """An inline SVG icon. Decorative: hidden from screen readers (put the label on the parent)."""
    if name in FILLED:
        # A thin matching outline rounds the corners of the solid arrows.
        paths, fill, stroke = FILLED[name], "currentColor", "currentColor" if name.startswith("arrow-") else "none"
    elif name in STROKE:
        paths, fill, stroke = STROKE[name], "none", "currentColor"
    elif name in BRAND_STROKE:
        paths, fill, stroke = BRAND_STROKE[name], "none", "currentColor"
    else:
        return ""
    return format_html(
        '<svg class="icon icon--{} {}" viewBox="0 0 24 24" width="{}" height="{}" fill="{}" stroke="{}" '
        'stroke-width="{}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
        '<path d="{}"></path></svg>',
        name,
        css_class,
        size,
        size,
        fill,
        stroke,
        "0.7" if name.startswith("arrow-") else "1.7",
        mark_safe(paths),
    )
