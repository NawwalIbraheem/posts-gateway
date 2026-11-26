"""
Turns every error into JSON with one consistent shape:
    {"error": "<short_code>", "detail": "<message>"}
"""

from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .upstream import UpstreamError, UpstreamNotFound


class BadRequest(Exception):
    """An invalid query parameter. Maps to 400."""


def _error(code, detail, http_status):
    return Response({"error": code, "detail": detail}, status=http_status)


def api_exception_handler(exc, context):
    """DRF exception handler (set in settings.REST_FRAMEWORK)."""
    if isinstance(exc, UpstreamNotFound):
        return _error("not_found", "The requested resource does not exist.", status.HTTP_404_NOT_FOUND)
    if isinstance(exc, UpstreamError):
        return _error("bad_gateway", str(exc), status.HTTP_502_BAD_GATEWAY)
    if isinstance(exc, BadRequest):
        return _error("bad_request", str(exc), status.HTTP_400_BAD_REQUEST)

    response = drf_exception_handler(exc, context)
    if response is not None:
        detail = response.data.get("detail", response.data) if isinstance(response.data, dict) else response.data
        response.data = {"error": "error", "detail": str(detail)}
    return response


# For URLs that don't match any endpoint (Django-level, not DRF)
def not_found_view(request, exception=None):
    return JsonResponse({"error": "not_found", "detail": f"No endpoint matches {request.path}"}, status=404)


def server_error_view(request):
    return JsonResponse({"error": "internal_error", "detail": "An unexpected error occurred."}, status=500)