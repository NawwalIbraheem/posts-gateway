from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("", include("gateway.urls")),
    # Bonus: OpenAPI schema + Swagger UI
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

# Return JSON instead of Django's HTML error pages
handler404 = "gateway.exceptions.not_found_view"
handler500 = "gateway.exceptions.server_error_view"