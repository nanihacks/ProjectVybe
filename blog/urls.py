from django.urls import path

from . import views
from .feeds import LatestPostsFeed


app_name = "blog"

# The fixed paths come before <slug>, so no post can shadow them (see Post.clean).
urlpatterns = [
    path("", views.post_list, name="list"),
    path("feed/", LatestPostsFeed(), name="feed"),
    path("category/<slug:slug>/", views.category_posts, name="category"),
    path("tag/<slug:slug>/", views.tag_posts, name="tag"),
    path("<slug:slug>/", views.post_detail, name="detail"),
]
