from django import template

from core.faq import faqs_for
from core.seo import json_ld_string


register = template.Library()


@register.inclusion_tag("components/faq.html")
def faq_section(placement, heading="Frequently asked questions", intro=""):
    """The FAQ list for a page. Renders nothing when no FAQ is ticked for it."""
    faqs = faqs_for(placement)
    structured = ""
    if faqs:
        structured = json_ld_string(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": faq.question,
                        "acceptedAnswer": {"@type": "Answer", "text": faq.answer},
                    }
                    for faq in faqs
                ],
            }
        )
    return {"faqs": faqs, "heading": heading, "intro": intro, "structured": structured, "placement": placement}
