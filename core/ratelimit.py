from django.conf import settings
from django.core.cache import cache


def client_ip(request):
    """Return the visitor's IP, trusting only the configured number of proxies."""
    remote_addr = request.META.get("REMOTE_ADDR", "")
    proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    if not proxies:
        return remote_addr
    forwarded = [
        part.strip()
        for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        if part.strip()
    ]
    if len(forwarded) >= proxies:
        return forwarded[-proxies]
    return remote_addr


def is_rate_limited(request, scope, limit, window_seconds):
    """Count this request; return True once the IP exceeds `limit` in the window."""
    key = f"rl:{scope}:{client_ip(request)}"
    if cache.add(key, 1, window_seconds):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.add(key, 1, window_seconds)
        return False
    return count > limit
