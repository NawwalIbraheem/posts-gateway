from drf_spectacular.utils import OpenApiParameter, PolymorphicProxySerializer, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from . import upstream
from .exceptions import BadRequest
from .pagination import paginate
from .serializers import (
    ErrorSerializer,
    HealthSerializer,
    PaginatedPostsSerializer,
    PostDetailSerializer,
    PostSerializer,
)

ERRORS = {404: ErrorSerializer, 502: ErrorSerializer}


def _parse_positive_int(value, name):
    """None if absent, BadRequest (400) if invalid."""
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except ValueError:
        raise BadRequest(f"'{name}' must be an integer.")
    if number < 1:
        raise BadRequest(f"'{name}' must be a positive integer.")
    return number


class HealthView(APIView):
    @extend_schema(operation_id="health", summary="Health check", responses={200: HealthSerializer})
    def get(self, request):
        return Response({"status": "ok"})


class PostListView(APIView):
    @extend_schema(
        operation_id="posts_list",
        summary="List posts",
        description="Filter with `userId`. Send `page` or `page_size` to get a paginated response.",
        parameters=[
            OpenApiParameter("userId", int, description="Only posts by this user."),
            OpenApiParameter("page", int, description="Page number (starts at 1)."),
            OpenApiParameter("page_size", int, description="Items per page (default 10, max 100)."),
        ],
        responses={
            200: PolymorphicProxySerializer(
                component_name="PostListResponse",
                serializers=[PostSerializer(many=True), PaginatedPostsSerializer],
                resource_type_field_name=None,
                many=False,
            ),
            400: ErrorSerializer,
            502: ErrorSerializer,
        },
    )
    def get(self, request):
        user_id = _parse_positive_int(request.query_params.get("userId"), "userId")
        posts = upstream.get_posts(user_id=user_id)
        return paginate(request, posts)


class PostDetailView(APIView):
    @extend_schema(
        operation_id="posts_retrieve",
        summary="One post with its author and comment count",
        responses={200: PostDetailSerializer, **ERRORS},
    )
    def get(self, request, post_id):
        post = upstream.get_post(post_id)
        author = upstream.get_user(post["userId"])
        comments = upstream.get_post_comments(post_id)

        return Response({
            **post,
            "author": {
                "id": author.get("id"),
                "name": author.get("name"),
                "email": author.get("email"),
            },
            "comment_count": len(comments),
        })


class UserPostListView(APIView):
    @extend_schema(
        operation_id="users_posts_list",
        summary="All posts written by a user",
        description="Returns 404 if the user does not exist.",
        responses={200: PostSerializer(many=True), **ERRORS},
    )
    def get(self, request, user_id):
        # Upstream returns [] for unknown users, so check the user exists first -> proper 404.
        upstream.get_user(user_id)
        return Response(upstream.get_posts(user_id=user_id))
