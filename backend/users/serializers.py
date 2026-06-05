from rest_framework import serializers
from .models import User, UserProfile

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
    password = serializers.CharField(write_only=True, min_length=8, required=False)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        if "password" not in validated_data:
            raise serializers.ValidationError({"password": "This field is required."})
        user = User.objects.create_user(**validated_data)
        UserProfile.objects.create(user=user) # Auto-initialize profile
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance

