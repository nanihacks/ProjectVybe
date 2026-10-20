import re

from django import forms

from catalog.models import Project, ProjectAddon, Service

from .models import Lead, PrivacyRequest


CONSENT_REQUIRED_ERROR = "Please tick this box so we can respond to your enquiry."
CONSENT_CONTACT_LABEL = (
    "I agree to the Privacy Policy and to ProjectVybe contacting me by "
    "WhatsApp, phone or email about this enquiry."
)
CONSENT_AGE_LABEL = (
    "I am 18 or older, or my parent or guardian agrees to me sharing these details."
)
CONSENT_MARKETING_LABEL = (
    "Send me occasional updates about new projects and courses."
)


class LeadForm(forms.ModelForm):
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        required=False,
        empty_label="General enquiry",
        label="Project",
    )
    selected_services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Services",
        help_text="Tick any services you'd like to discuss.",
    )
    selected_addons = forms.ModelMultipleChoiceField(
        queryset=ProjectAddon.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Project add-ons",
        help_text="Tick any add-ons you'd like to discuss.",
    )
    message = forms.CharField(
        min_length=10,
        label="Message",
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "Tell us a little about what you are exploring.",
            }
        ),
    )
    # Consent boxes are never pre-ticked (Indian dark-pattern rules, DPDP Act).
    consent_contact = forms.BooleanField(
        required=True,
        label=CONSENT_CONTACT_LABEL,
        error_messages={"required": CONSENT_REQUIRED_ERROR},
    )
    consent_age = forms.BooleanField(
        required=True,
        label=CONSENT_AGE_LABEL,
        error_messages={"required": CONSENT_REQUIRED_ERROR},
    )
    consent_marketing = forms.BooleanField(
        required=False,
        label=CONSENT_MARKETING_LABEL,
    )
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

    class Meta:
        model = Lead
        fields = (
            "name",
            "email",
            "phone",
            "project",
            "selected_services",
            "selected_addons",
            "message",
        )
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = (
            Project.objects.filter(
                is_published=True,
                category__is_active=True,
            )
            .select_related("category")
            .order_by("-created_at", "title")
        )
        self.fields["selected_services"].queryset = Service.objects.filter(
            is_active=True
        ).order_by("ordering", "name")

        if project is None:
            project_id = self.data.get("project") if self.is_bound else self.initial.get("project")
            if project_id:
                project = self.fields["project"].queryset.filter(pk=project_id).first()

        addon_queryset = ProjectAddon.objects.filter(is_active=True)
        if project is not None:
            self.fields["phone"].required = True
            addon_queryset = addon_queryset.filter(projects=project)
        else:
            addon_queryset = addon_queryset.none()
        self.fields["selected_addons"].queryset = addon_queryset.order_by(
            "ordering", "name"
        )

        for field_name, field in self.fields.items():
            if field_name == "website":
                continue
            if field.help_text:
                field.widget.attrs["aria-describedby"] = f"id_{field_name}_help"

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if phone and (
            not re.fullmatch(r"[0-9+().\-\s]{7,40}", phone)
            or len(re.sub(r"\D", "", phone)) < 7
        ):
            raise forms.ValidationError("Enter a valid phone number or leave this field blank.")
        return phone

    def clean_message(self):
        message = self.cleaned_data.get("message", "").strip()
        if len(message) < 10:
            raise forms.ValidationError("Add a little more detail (at least 10 characters).")
        return message

    def clean(self):
        cleaned_data = super().clean()
        for field_name in self.errors:
            if field_name not in self.fields or field_name == "website":
                continue
            described_by = []
            if self.fields[field_name].help_text:
                described_by.append(f"id_{field_name}_help")
            described_by.append(f"id_{field_name}_error")
            self.fields[field_name].widget.attrs["aria-invalid"] = "true"
            self.fields[field_name].widget.attrs["aria-describedby"] = " ".join(
                described_by
            )
        if cleaned_data.get("website"):
            raise forms.ValidationError("This enquiry could not be submitted.")
        return cleaned_data

    def consent_text(self):
        """Wording shown to the visitor, stored with the consent record."""
        lines = [
            f"[required] {CONSENT_CONTACT_LABEL}",
            f"[required] {CONSENT_AGE_LABEL}",
            f"[optional] {CONSENT_MARKETING_LABEL}",
        ]
        return "\n".join(lines)


class PrivacyRequestForm(forms.ModelForm):
    """Public form for asking to see, correct, delete or stop using your information."""

    kind = forms.ChoiceField(
        choices=PrivacyRequest.Kind.choices,
        widget=forms.RadioSelect,
        label="What would you like us to do?",
        error_messages={"required": "Please choose one option."},
    )
    reference = forms.CharField(
        required=False,
        max_length=20,
        label="Enquiry reference (optional)",
        help_text="For example PV-1042, from your confirmation email.",
    )
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

    class Meta:
        model = PrivacyRequest
        fields = ("kind", "email", "reference", "message")
        labels = {
            "email": "Your email address",
            "message": "Anything else we should know (optional)",
        }
        help_texts = {
            "email": "The address you used when you contacted us. We will reply here.",
        }
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != "website" and field.help_text:
                field.widget.attrs["aria-describedby"] = f"id_{field_name}_help"

    def clean_reference(self):
        reference = self.cleaned_data.get("reference", "").strip().upper()
        if reference and not re.fullmatch(r"PV-\d{4,10}", reference):
            raise forms.ValidationError("Enter a reference like PV-1042, or leave this blank.")
        return reference

    def clean(self):
        cleaned_data = super().clean()
        for field_name in self.errors:
            if field_name not in self.fields or field_name == "website":
                continue
            described_by = []
            if self.fields[field_name].help_text:
                described_by.append(f"id_{field_name}_help")
            described_by.append(f"id_{field_name}_error")
            self.fields[field_name].widget.attrs["aria-invalid"] = "true"
            self.fields[field_name].widget.attrs["aria-describedby"] = " ".join(described_by)
        if cleaned_data.get("website"):
            raise forms.ValidationError("This request could not be submitted.")
        return cleaned_data

