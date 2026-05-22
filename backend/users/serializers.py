from rest_framework import serializers
from .models import User, UserProfile, SavedExperience

class UserProfileResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['id', 'bio', 'target_role', 'batch_year']

class UserResponseSerializer(serializers.ModelSerializer):
    profile = UserProfileResponseSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'middle_name', 'profile', 'created_at']

class UserUpsertSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        UserProfile.objects.create(user=user) # Auto-initialize profile
        return user

class SavedExperienceResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedExperience
        fields = ['id', 'experience', 'notes', 'created_at']

class SavedExperienceUpsertSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedExperience
        fields = ['experience', 'notes']