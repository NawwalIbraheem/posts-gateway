"""
Optional pagination. If neither `page` nor `page_size` is sent,
the full list is returned unchanged.
"""

import math

from rest_framework.response import Response

from .exceptions import BadRequest

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def _read_int(request, name, default):
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise BadRequest(f"'{name}' must be an integer.")
    if value < 1:
        raise BadRequest(f"'{name}' must be a positive integer.")
    return value


def paginate(request, items):
    if "page" not in request.query_params and "page_size" not in request.query_params:
        return Response(items)

    page = _read_int(request, "page", 1)
    page_size = min(_read_int(request, "page_size", DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)

    count = len(items)
    total_pages = max(1, math.ceil(count / page_size))
    start = (page - 1) * page_size
    results = items[start : start + page_size]

    def page_link(number):
        if number < 1 or number > total_pages:
            return None
        query = request.query_params.copy()
        query["page"] = number
        query["page_size"] = page_size
        return request.build_absolute_uri(f"{request.path}?{query.urlencode()}")

    return Response({
        "count": count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "next": page_link(page + 1),
        "previous": page_link(page - 1),
        "results": results,
    })