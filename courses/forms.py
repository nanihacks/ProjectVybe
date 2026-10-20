from django import forms

from core.validators import StrictEmailField, StrictPhoneField
from leads.forms import CONSENT_AGE_LABEL, CONSENT_MARKETING_LABEL


CONSENT_REQUIRED_ERROR = "Please tick this box to continue."


CONSENT_CONTACT_LABEL = (
    "I agree to the Privacy Policy and to ProjectVybe emailing me about this course "
    "and when it opens."
)


class WaitlistForm(forms.Form):
    name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    email = StrictEmailField()
    phone = StrictPhoneField(required=False, label="Phone (optional)")
    # Consent boxes are never pre-ticked.
    consent_contact = forms.BooleanField(
        label=CONSENT_CONTACT_LABEL, error_messages={"required": CONSENT_REQUIRED_ERROR}
    )
    consent_age = forms.BooleanField(
        label=CONSENT_AGE_LABEL, error_messages={"required": CONSENT_REQUIRED_ERROR}
    )
    consent_marketing = forms.BooleanField(required=False, label=CONSENT_MARKETING_LABEL)
    website = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={
                "class": "form-honeypot__input",
                "tabindex": "-1",
                "autocomplete": "off",
                "aria-hidden": "true",
            }
        ),
    )

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def clean(self):
        cleaned = super().clean()
        for field_name in self.errors:
            if field_name not in self.fields or field_name == "website":
                continue
            self.fields[field_name].widget.attrs["aria-invalid"] = "true"
            self.fields[field_name].widget.attrs["aria-describedby"] = f"id_{field_name}_error"
        if cleaned.get("website"):
            raise forms.ValidationError("This could not be submitted.")
        return cleaned

    def consent_text(self):
        return "\n".join(
            [
                f"[required] {CONSENT_CONTACT_LABEL}",
                f"[required] {CONSENT_AGE_LABEL}",
                f"[optional] {CONSENT_MARKETING_LABEL}",
            ]
        )
