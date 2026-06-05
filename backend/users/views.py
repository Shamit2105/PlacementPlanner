import logging
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction

from base.exceptions import PRValidationError
from .models import User
from .serializers import (
    UserUpsertSerializer, UserResponseSerializer,
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

