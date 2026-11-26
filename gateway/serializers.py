from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField(default="ok")


class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField()
    detail = serializers.CharField()


class PostSerializer(serializers.Serializer):
    userId = serializers.IntegerField()
    id = serializers.IntegerField()
    title = serializers.CharField()
    body = serializers.CharField()


class AuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()


class PostDetailSerializer(PostSerializer):
    author = AuthorSerializer()
    comment_count = serializers.IntegerField()


class PaginatedPostsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = PostSerializer(many=True)