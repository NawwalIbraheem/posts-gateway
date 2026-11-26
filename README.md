# Posts Gateway

A small Django REST service that acts as a gateway to the public
[JSONPlaceholder](https://jsonplaceholder.typicode.com) API. It fetches posts, users and comments from the upstream API, reshapes them, and exposes them through its own endpoints on port **8000**. The whole service runs in Docker.

## Features

- 4 JSON endpoints: `/health`, `/posts`, `/posts/{id}`, `/users/{id}/posts`
- Correct status codes: `200` success, `400` invalid query parameter, `404` unknown ID, `502` upstream failure
- Upstream timeouts and errors handled gracefully (the service never crashes)
- Upstream base URL read from the `UPSTREAM_API_URL` environment variable
- **Bonus:** 60-second in-memory caching of upstream responses
- **Bonus:** optional pagination on `/posts`
- **Bonus:** 17 unit tests with the upstream API mocked
- **Bonus:** Swagger UI at `/docs` (OpenAPI schema at `/schema`)
- **Bonus:** GitHub Actions CI: runs the tests, builds the image and smoke-tests the container

## Tech stack

Python 3.12 · Django 5.2 · Django REST Framework · requests · drf-spectacular · gunicorn · Docker

## Run with Docker

Requirements: Docker with the Compose plugin.

```bash
git clone https://github.com/NawwalIbraheem/posts-gateway.git
cd posts-gateway
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/posts/1
```

- Stop: `docker compose down`
- Logs: `docker compose logs -f`
- Tests inside the container: `docker compose exec api python manage.py test`

## Run locally (optional)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
export UPSTREAM_API_URL=https://jsonplaceholder.typicode.com
                                   # Windows PowerShell: $env:UPSTREAM_API_URL="https://jsonplaceholder.typicode.com"
python manage.py runserver 8000
```

Run the tests with `python manage.py test` (no network needed).

## Configuration

All configuration is done with environment variables (see `.env.example`).

| Variable               | Default      | Description |
|------------------------|--------------|-------------|
| `UPSTREAM_API_URL`     | *(required)* | Base URL of the upstream API |
| `UPSTREAM_TIMEOUT`     | `5`          | Seconds to wait for the upstream before returning `502` |
| `CACHE_TTL`            | `60`         | Seconds to cache upstream responses (`0` disables caching) |
| `DJANGO_SECRET_KEY`    | dev key      | Django secret key |
| `DJANGO_DEBUG`         | `false`      | Django debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Allowed hosts |
| `GUNICORN_WORKERS`     | `2`          | Gunicorn worker processes |
| `LOG_LEVEL`            | `INFO`       | Log level |

## Endpoints

Interactive documentation: **http://localhost:8000/docs**

### `GET /health`

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok"}
```

### `GET /posts`

Returns all posts. Optional query parameters: `userId` (filter by author), `page` and
`page_size` (pagination; default page size 10, max 100). Without `page`/`page_size`
the plain list is returned.

```bash
curl "http://localhost:8000/posts?userId=1"
```

```json
[
  {
    "userId": 1,
    "id": 1,
    "title": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
    "body": "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\n..."
  }
]
```

Paginated:

```bash
curl "http://localhost:8000/posts?page=2&page_size=5"
```

```json
{
  "count": 100,
  "page": 2,
  "page_size": 5,
  "total_pages": 20,
  "next": "http://localhost:8000/posts?page=3&page_size=5",
  "previous": "http://localhost:8000/posts?page=1&page_size=5",
  "results": [{"userId": 2, "id": 6, "title": "...", "body": "..."}]
}
```

### `GET /posts/{id}`

Returns one post with its author's name and email and its comment count.

```bash
curl http://localhost:8000/posts/1
```

```json
{
  "userId": 1,
  "id": 1,
  "title": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
  "body": "quia et suscipit\n...",
  "author": {"id": 1, "name": "Leanne Graham", "email": "Sincere@april.biz"},
  "comment_count": 5
}
```

### `GET /users/{id}/posts`

Returns all posts written by that user.

```bash
curl http://localhost:8000/users/1/posts
```

```json
[
  {"userId": 1, "id": 1, "title": "...", "body": "..."},
  {"userId": 1, "id": 2, "title": "...", "body": "..."}
]
```

### Errors

All errors are JSON with the same shape:

```bash
curl -i http://localhost:8000/posts/9999
```

```
HTTP/1.1 404 Not Found
{"error": "not_found", "detail": "The requested resource does not exist."}
```

| Status | `error`       | When |
|--------|---------------|------|
| 400    | `bad_request` | A query parameter is not a positive integer (e.g. `?userId=abc`) |
| 404    | `not_found`   | Unknown post or user ID, or unknown URL |
| 502    | `bad_gateway` | Upstream timed out, unreachable, returned 5xx or invalid JSON |

## Project structure

```
config/              Django project: settings, root URLs, WSGI
gateway/
  upstream.py        Upstream client: timeout, error mapping, caching
  views.py           API endpoints
  pagination.py      Optional pagination for /posts
  exceptions.py      Maps errors to JSON responses (400/404/502)
  serializers.py     Response shapes for the /docs page
  tests.py           Unit tests (upstream mocked)
Dockerfile
docker-compose.yml
.github/workflows/ci.yml
```

## Assumptions and decisions

- **No database.** The service is a stateless gateway, so no models or migrations are needed.
- **Django REST Framework** for JSON views; **drf-spectacular** for the OpenAPI schema and Swagger UI.
- **`/posts/{id}` makes three upstream calls**: the post, its author (`/users/{userId}`) and its comments (`/posts/{id}/comments`). Only the author's `id`, `name` and `email` are returned.
- **`/users/{id}/posts` checks that the user exists first.** JSONPlaceholder returns an empty list for unknown users, so without this check the endpoint could never return `404`.
- **404 vs 502.** An upstream `404` becomes `404`. Timeouts, connection errors, upstream `5xx` and invalid JSON become `502`. A missing `UPSTREAM_API_URL` also returns `502` instead of crashing.
- **Invalid query parameters return `400`**, since `200` or `502` would be misleading for `?userId=abc`.
- **Pagination is opt-in**, so `/posts` without `page`/`page_size` behaves exactly as specified.
- **Caching** uses Django's in-memory cache (`LocMemCache`). Only successful responses are cached, so a short outage is not remembered. Each gunicorn worker has its own cache; Redis would be the next step for production.
- **URLs have no trailing slash** (`/posts`, not `/posts/`), matching the spec.
- **gunicorn** serves the app in the container (not Django's dev server), and the container runs as a non-root user with a health check on `/health`.
