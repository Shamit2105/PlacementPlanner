from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import (TokenObtainPairView,TokenRefreshView)

# Import your newly refactored ViewSets
from users.views import UserViewSet, SavedExperienceViewSet
from companies.views import CompanyViewSet, PlacementExperienceViewSet

# Import your custom AI RAG endpoint
#from companies.views import placement_bot_query

# ==========================================
# API ROUTER CONFIGURATION
# ==========================================
# The DefaultRouter automatically generates all the CRUD URLs
# e.g., GET /api/users/, POST /api/users/, GET /api/users/1/

router = DefaultRouter()

# Users App
router.register(r'users', UserViewSet, basename='user')
#router.register(r'bookmarks', SavedExperienceViewSet, basename='bookmark')

# Companies App
router.register(r'companies', CompanyViewSet, basename='company')
router.register(r'experiences', PlacementExperienceViewSet, basename='experience')

# ==========================================
# URL PATTERNS
# ==========================================
urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # 1. Main REST API (Handles all the router endpoints above)
    path('api/', include(router.urls)),

    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    
    # This generates a new Access token when the old one expires.
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 2. Custom AI RAG Endpoint
    #path('api/bot/ask/', placement_bot_query, name='ask_bot'),

    # 3. Swagger Documentation (OpenAPI 3.0)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'), # The raw JSON schema
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'), # The visual UI
]