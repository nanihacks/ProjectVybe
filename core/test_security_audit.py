from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import validate_link_target
from .signals import _clean
from .testing import force_login_verified


def staff_with(*codenames):
    user = get_user_model().objects.create_user(
        username="staff-" + "-".join(codenames), password="x", is_staff=True
    )
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    return user


class ViewOnlyStaffTests(TestCase):
    def actions_for(self, user, changelist):
        force_login_verified(self.client, user)
        response = self.client.get(reverse(changelist), secure=True)
        self.assertEqual(response.status_code, 200)
        form = response.context["action_form"]  # None when no action is available
        return [name for name, _ in form.fields["action"].choices] if form else []

    def test_view_only_staff_do_not_get_state_changing_actions(self):
        cases = {
            "admin:orders_order_changelist": ("view_order", "issue_refund"),
            "admin:leads_lead_changelist": ("view_lead", "anonymise_selected"),
            "admin:blog_post_changelist": ("view_post", "publish_now"),
            "admin:catalog_project_changelist": ("view_project", "publish_projects"),
            "admin:legal_legalpage_changelist": ("view_legalpage", "publish_drafts"),
            "admin:courses_coursewaitlistentry_changelist": ("view_coursewaitlistentry", "anonymise_selected"),
        }
        for index, (changelist, (perm, action)) in enumerate(cases.items()):
            user = get_user_model().objects.create_user(username=f"viewer{index}", password="x", is_staff=True)
            user.user_permissions.add(Permission.objects.get(codename=perm))
            self.assertNotIn(action, self.actions_for(user, changelist), changelist)

    def test_email_previews_need_model_permission(self):
        user = get_user_model().objects.create_user(username="blogger", password="x", is_staff=True)
        force_login_verified(self.client, user)
        url = reverse("admin:email_preview_detail", args=["order-paid-owner"])
        self.assertEqual(self.client.get(url, secure=True).status_code, 404)

        user.user_permissions.add(Permission.objects.get(codename="view_order"))
        user = get_user_model().objects.get(pk=user.pk)
        force_login_verified(self.client, user)
        self.assertEqual(self.client.get(url, secure=True).status_code, 200)


class LinkAndLogTests(TestCase):
    def test_link_validator(self):
        for good in ("", "/projects/", "https://example.com/a", "http://example.com"):
            validate_link_target(good)
        for bad in ("javascript:alert(1)", "data:text/html,x", "//evil.example", "/\\evil", "ftp://x", "projects"):
            with self.assertRaises(ValidationError, msg=bad):
                validate_link_target(bad)

    def test_log_text_loses_control_characters(self):
        self.assertEqual(_clean("x\nINFO fake\r"), "xINFO fake")
        self.assertEqual(len(_clean("a" * 500)), 80)
