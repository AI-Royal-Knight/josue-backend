from urllib.parse import urlparse
from django.conf import settings


def get_frontend_url(request=None) -> str:
    """
    Determines the appropriate frontend base URL.
    1. If a request is provided:
       - Inspects 'Origin' and 'Referer' headers.
       - If origin/referer matches a known host pattern (tresta.cloud, localhost, 127.0.0.1),
         uses that scheme and host so local development and production environments automatically
         get the right URLs.
    2. Otherwise, falls back to settings.FRONTEND_URL.
    3. Defaults to 'https://tresta.cloud'.
    """
    if request:
        origin = request.headers.get("origin") or request.META.get("HTTP_ORIGIN")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme and parsed.netloc:
                netloc = parsed.netloc.lower()
                if "tresta.cloud" in netloc or "localhost" in netloc or "127.0.0.1" in netloc:
                    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

        referer = request.headers.get("referer") or request.META.get("HTTP_REFERER")
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                netloc = parsed.netloc.lower()
                if "tresta.cloud" in netloc or "localhost" in netloc or "127.0.0.1" in netloc:
                    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    configured = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    if configured:
        return configured

    return "https://tresta.cloud"


def get_default_from_email() -> str:
    """
    Returns the configured default from email, falling back to info@tresta.cloud.
    """
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or "info@tresta.cloud"
