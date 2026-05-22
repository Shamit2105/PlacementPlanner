import logging
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Company, PlacementExperience
from .serializers import CompanyResponseSerializer, PlacementExperienceResponseSerializer

logger = logging.getLogger('companies')

class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for companies. Creation is handled strictly by backend scrapers.
    """
    queryset = Company.objects.all().order_by('name')
    serializer_class = CompanyResponseSerializer
    permission_classes = [AllowAny]

class PlacementExperienceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for experiences. Implements select_related for database optimization.
    """
    queryset = PlacementExperience.objects.select_related('company').filter(is_extracted=True).order_by('-created_at')
    serializer_class = PlacementExperienceResponseSerializer
    permission_classes = [AllowAny]
    filterset_fields = ['company__id', 'round_type']

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error fetching experiences: {str(e)}", exc_info=True)
            return Response({"message": "Failed to retrieve experiences."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)