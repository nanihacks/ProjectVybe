def category_asset_folder(instance):
    return "projectvybe/categories"


def project_asset_folder(instance):
    slug = getattr(instance, "slug", None) or "unassigned"
    return f"projectvybe/projects/{slug}"


def project_gallery_asset_folder(instance):
    project = getattr(instance, "project", None)
    slug = getattr(project, "slug", None) or "unassigned"
    return f"projectvybe/projects/{slug}"


def service_asset_folder(instance):
    return "projectvybe/services"
