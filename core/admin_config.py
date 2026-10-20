from django.contrib.admin.apps import AdminConfig


class ProjectVybeAdminConfig(AdminConfig):
    # A dotted path: the site class is imported only after all apps are loaded.
    default_site = "core.admin_site.ProjectVybeAdminSite"
