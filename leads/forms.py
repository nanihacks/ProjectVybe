import re

from django import forms

from catalog.models import Project, ProjectAddon, Service

from .models import Lead


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
        label="Company services",
        help_text="Select any company service you would like to discuss.",
    )
    selected_addons = forms.ModelMultipleChoiceField(
        queryset=ProjectAddon.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Project add-ons",
        help_text="Select project-specific add-ons you would like to discuss.",
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
            raise forms.ValidationError("Please provide at least 10 characters of context.")
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
