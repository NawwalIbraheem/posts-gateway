"""
Unit tests. The upstream API is always mocked, so the tests never use
the network. Run with:  python manage.py test
"""

from unittest import mock

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

UPSTREAM = "https://upstream.test"

POSTS = [
    {"userId": 1, "id": 1, "title": "first", "body": "body 1"},
    {"userId": 1, "id": 2, "title": "second", "body": "body 2"},
    {"userId": 2, "id": 3, "title": "third", "body": "body 3"},
]
USER_1 = {"id": 1, "name": "Leanne Graham", "email": "Sincere@april.biz", "username": "Bret"}
COMMENTS_POST_1 = [{"id": 1, "postId": 1}, {"id": 2, "postId": 1}, {"id": 3, "postId": 1}]


def fake_response(status_code=200, json_data=None, invalid_json=False):
    response = mock.Mock(status_code=status_code)
    if invalid_json:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = json_data
    return response


def fake_upstream(url, params=None, timeout=None):
    """A tiny fake JSONPlaceholder."""
    path = url.removeprefix(UPSTREAM)
    if path == "/posts":
        if params and "userId" in params:
            return fake_response(json_data=[p for p in POSTS if p["userId"] == params["userId"]])
        return fake_response(json_data=POSTS)
    if path == "/posts/1":
        return fake_response(json_data=POSTS[0])
    if path == "/posts/1/comments":
        return fake_response(json_data=COMMENTS_POST_1)
    if path == "/users/1":
        return fake_response(json_data=USER_1)
    return fake_response(status_code=404, json_data={})


@override_settings(UPSTREAM_API_URL=UPSTREAM, CACHE_TTL=60)
class GatewayTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch("gateway.upstream.requests.get", side_effect=fake_upstream)
        self.mock_get = patcher.start()
        self.addCleanup(patcher.stop)


class HealthTests(GatewayTestCase):
    def test_health_returns_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.mock_get.assert_not_called()


class PostListTests(GatewayTestCase):
    def test_returns_all_posts(self):
        response = self.client.get("/posts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), POSTS)

    def test_filters_by_user_id(self):
        response = self.client.get("/posts?userId=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.json()], [3])

    def test_invalid_user_id_returns_400(self):
        response = self.client.get("/posts?userId=abc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "bad_request")

    def test_pagination(self):
        response = self.client.get("/posts?page=2&page_size=2")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(body["total_pages"], 2)
        self.assertEqual([p["id"] for p in body["results"]], [3])
        self.assertIsNone(body["next"])

    def test_invalid_page_returns_400(self):
        self.assertEqual(self.client.get("/posts?page=0").status_code, 400)


class PostDetailTests(GatewayTestCase):
    def test_returns_post_with_author_and_comment_count(self):
        response = self.client.get("/posts/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            **POSTS[0],
            "author": {"id": 1, "name": "Leanne Graham", "email": "Sincere@april.biz"},
            "comment_count": 3,
        })

    def test_unknown_post_returns_404(self):
        response = self.client.get("/posts/9999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "not_found")


class UserPostsTests(GatewayTestCase):
    def test_returns_posts_for_user(self):
        response = self.client.get("/users/1/posts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.json()], [1, 2])

    def test_unknown_user_returns_404(self):
        self.assertEqual(self.client.get("/users/9999/posts").status_code, 404)


class UpstreamFailureTests(GatewayTestCase):
    def test_timeout_returns_502(self):
        self.mock_get.side_effect = requests.Timeout("too slow")
        response = self.client.get("/posts")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], "bad_gateway")

    def test_connection_error_returns_502(self):
        self.mock_get.side_effect = requests.ConnectionError("down")
        self.assertEqual(self.client.get("/posts/1").status_code, 502)

    def test_upstream_500_returns_502(self):
        self.mock_get.side_effect = None
        self.mock_get.return_value = fake_response(status_code=500)
        self.assertEqual(self.client.get("/posts").status_code, 502)

    def test_invalid_json_returns_502(self):
        self.mock_get.side_effect = None
        self.mock_get.return_value = fake_response(invalid_json=True)
        self.assertEqual(self.client.get("/posts").status_code, 502)


class CachingTests(GatewayTestCase):
    def test_second_request_is_served_from_cache(self):
        self.client.get("/posts")
        self.client.get("/posts")
        self.assertEqual(self.mock_get.call_count, 1)

    def test_failures_are_not_cached(self):
        self.mock_get.side_effect = requests.Timeout("too slow")
        self.assertEqual(self.client.get("/posts").status_code, 502)
        self.mock_get.side_effect = fake_upstream
        self.assertEqual(self.client.get("/posts").status_code, 200)


class DocsTests(GatewayTestCase):
    def test_docs_page_and_schema_are_served(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(self.client.get("/schema").status_code, 200)
