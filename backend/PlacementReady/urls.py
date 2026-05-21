from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView 

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- SWAGGER URLS ---
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'), # The raw JSON schema
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'), # The beautiful UI
]

