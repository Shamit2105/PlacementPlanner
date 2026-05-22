import logging
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction

from base.exceptions import PRValidationError
from .models import User, SavedExperience
from .serializers import (
    UserUpsertSerializer, UserResponseSerializer,
    SavedExperienceUpsertSerializer, SavedExperienceResponseSerializer
)

logger = logging.getLogger('users')

class UserViewSet(
    viewsets.GenericViewSet,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin
):
    queryset = User.objects.all()

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return UserUpsertSerializer
        return UserResponseSerializer

    def create(self, request, *args, **kwargs):
        try:
            logger.info("User registration initiated.")
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            with transaction.atomic():
                user = serializer.save()

            logger.info(f"Successfully created user: {user.email}")
            response_serializer = UserResponseSerializer(user, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.critical(f"Registration failed. Error: {str(e)}", exc_info=True)
            return Response({"message": "Registration failed. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SavedExperienceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedExperience.objects.filter(user=self.request.user).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SavedExperienceUpsertSerializer
        return SavedExperienceResponseSerializer

    def create(self, request, *args, **kwargs):
        try:
            logger.info(f"Bookmark creation called by: {request.user.email}")
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Force current user
            bookmark = serializer.save(user=request.user)
            
            response_serializer = SavedExperienceResponseSerializer(bookmark, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Bookmark creation failed for {request.user.email}: {str(e)}", exc_info=True)
            return Response({"message": "Failed to save experience."}, status=status.HTTP_400_BAD_REQUEST)