"""
Utilities to build externally-visible base URLs.

Links that are sent outside of the application (e.g. password reset emails)
must never be derived from the client-supplied Host header. With
django.contrib.sites uninstalled, get_current_site() returns a RequestSite
whose domain is simply request.get_host(), and with an unrestricted
ALLOWED_HOSTS an unauthenticated attacker can choose that header freely
(reset-link poisoning, CWE-640).

Use get_canonical_url_parts() whenever you need site_name / domain / protocol
for such links.
"""

from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest

_CANONICAL_BASE_URL_ERROR = (
    "AIRONE_CANONICAL_BASE_URL must be an absolute base URL like "
    "'https://pagoda.example.com' (scheme, host and no path)"
)
_CANONICAL_BASE_URL_REQUIRED = (
    "AIRONE_CANONICAL_BASE_URL is not configured. Refusing to build an "
    "externally-visible URL from the client-controlled Host header "
    "(reset-link poisoning, CWE-640). Set AIRONE_CANONICAL_BASE_URL to the "
    "canonical base URL of this deployment."
)


def get_canonical_url_parts(request: HttpRequest, use_https: bool = False) -> dict[str, Any]:
    """
    Return site_name / domain / protocol for building externally-visible URLs.

    - When AIRONE_CANONICAL_BASE_URL is configured, it is always used and the
      request is only consulted for the fallback branch below.
    - When it is not configured and CANONICAL_URL_FALLBACK is enabled
      (development only), the values fall back to get_current_site(request).
    - Otherwise, raise ImproperlyConfigured instead of trusting the
      attacker-controlled Host header.
    """
    base_url = str(getattr(settings, "CANONICAL_BASE_URL", "") or "")
    if base_url:
        # Accept values without an explicit scheme by defaulting to https.
        parts = urlsplit(base_url if "://" in base_url else f"https://{base_url}")
        if (
            parts.scheme not in ("http", "https")
            or not parts.netloc
            or parts.path
            not in (
                "",
                "/",
            )
        ):
            raise ImproperlyConfigured(_CANONICAL_BASE_URL_ERROR)

        return {
            "site_name": parts.netloc,
            "domain": parts.netloc,
            "protocol": parts.scheme,
        }

    if not getattr(settings, "CANONICAL_URL_FALLBACK", False):
        raise ImproperlyConfigured(_CANONICAL_BASE_URL_REQUIRED)

    # Development fallback: use the request host. This branch must not be
    # reachable in production (see CANONICAL_URL_FALLBACK).
    site = get_current_site(request)
    return {
        "site_name": site.name,
        "domain": site.domain,
        "protocol": "https" if use_https else "http",
    }
