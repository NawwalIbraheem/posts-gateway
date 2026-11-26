"""
Client for the upstream API (JSONPlaceholder).

Every upstream call goes through fetch(), which:
  * builds the URL from the UPSTREAM_API_URL setting,
  * applies a timeout so a slow upstream cannot hang the service,
  * turns every network/HTTP problem into one of two exceptions,
  * caches successful responses for CACHE_TTL seconds.
"""

import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class UpstreamError(Exception):
    """Upstream failed (timeout, connection error, 5xx, bad JSON). Maps to 502."""


class UpstreamNotFound(Exception):
    """Upstream answered 404. Maps to 404."""


def _build_url(path):
    base_url = settings.UPSTREAM_API_URL
    if not base_url:
        raise UpstreamError("UPSTREAM_API_URL is not configured")
    return f"{base_url}/{path.lstrip('/')}"


def fetch(path, params=None):
    """GET `path` from the upstream API and return the decoded JSON."""
    url = _build_url(path)
    cache_key = "upstream:" + url + ("?" + urlencode(sorted(params.items())) if params else "")

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT)
    except requests.Timeout as exc:
        logger.warning("Upstream timeout for %s: %s", url, exc)
        raise UpstreamError("The upstream API timed out") from exc
    except requests.RequestException as exc:
        logger.warning("Upstream request failed for %s: %s", url, exc)
        raise UpstreamError("Could not reach the upstream API") from exc

    if response.status_code == 404:
        raise UpstreamNotFound(f"Upstream resource not found: {path}")
    if response.status_code >= 400:
        logger.warning("Upstream returned %s for %s", response.status_code, url)
        raise UpstreamError(f"The upstream API returned status {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamError("The upstream API returned an invalid response") from exc

    # Only successful responses are cached, so an outage is not remembered.
    if settings.CACHE_TTL > 0:
        cache.set(cache_key, data, timeout=settings.CACHE_TTL)
    return data


def get_posts(user_id=None):
    params = {"userId": user_id} if user_id is not None else None
    return fetch("/posts", params=params)


def get_post(post_id):
    return fetch(f"/posts/{post_id}")


def get_user(user_id):
    return fetch(f"/users/{user_id}")


def get_post_comments(post_id):
    return fetch(f"/posts/{post_id}/comments")