"""Markdown for blog posts to sanitised HTML, plus a table of contents."""

import re

import markdown
from markdown.extensions.toc import slugify as default_slugify

from legal.rendering import ALLOWED_ATTRIBUTES, ALLOWED_TAGS, clean_html


BLOG_TAGS = ALLOWED_TAGS | {"img", "pre", "code", "figure", "figcaption", "del", "sup", "sub"}
BLOG_ATTRIBUTES = {
    **ALLOWED_ATTRIBUTES,
    "img": {"src", "alt", "width", "height"},
    "code": {"class"},
    "h2": {"id"},
    "h3": {"id"},
    "h4": {"id"},
}

HEADING_ID = re.compile(r"^s-[a-z0-9_-]+$")
CODE_CLASS = re.compile(r"^language-[a-z0-9+#_-]+$")
WORDS_PER_MINUTE = 220


def _prefixed_slug(value, separator):
    """Heading ids start with 's-' so they can never collide with ids used by the page itself."""
    return "s-" + default_slugify(value, separator)


def _attribute_filter(tag, attribute, value):
    if tag == "img" and attribute == "src":
        return value if value.startswith("https://") else None
    if tag == "code" and attribute == "class":
        classes = [name for name in value.split() if CODE_CLASS.match(name)]
        return " ".join(classes) or None
    if attribute == "id":
        return value if HEADING_ID.match(value) else None
    return value


def render_post(text):
    """(html, toc, reading_minutes) for Markdown `text`.

    `toc` is a list of {"id", "title"} for the second-level headings.
    """
    md = markdown.Markdown(
        extensions=["extra", "sane_lists", "toc", "fenced_code"],
        extension_configs={"toc": {"slugify": _prefixed_slug, "toc_depth": "2-4"}},
    )
    raw_html = md.convert(text or "")
    html = clean_html(
        raw_html,
        tags=BLOG_TAGS,
        attributes=BLOG_ATTRIBUTES,
        attribute_filter=_attribute_filter,
        set_tag_attribute_values={"img": {"loading": "lazy", "decoding": "async"}},
    )
    toc = [
        {"id": token["id"], "title": token["name"]}
        for token in md.toc_tokens
        if token["level"] == 2 and HEADING_ID.match(token["id"])
    ]
    words = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", html)))
    minutes = max(1, -(-words // WORDS_PER_MINUTE))
    return html, toc, minutes
