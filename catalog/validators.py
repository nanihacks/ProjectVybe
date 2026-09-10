from urllib.parse import urlparse

from django.core.exceptions import ValidationError


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be"}


def validate_youtube_url(value):
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in YOUTUBE_HOSTS:
        raise ValidationError("Enter a valid YouTube URL.")
