"""
Root URL Configuration
========================
All API routes live under /api/v1/ to allow versioning later.
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),

    # JWT auth endpoints (optional — skip if not using auth)
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Questions bank — CRUD + search
    path("api/questions/", include("companies.urls")),
    path("api/interviews/", include("interviews.urls")),
    path("api/users/", include("users.urls")),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'), # The raw JSON schema
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Mock interviews — create, answer, results
    #path("api/v1/interviews/", include("interviews.urls")),
]
