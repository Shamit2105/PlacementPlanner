from rest_framework import serializers

from .models import User,UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['username', 'first_name', 'last_name']


class UserUpsertSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True,min_length=8)

    class Meta:
        model = User
        fields = ['username','first_name','last_name']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
            )
        UserProfile.objects.create(user=user)
        return user

class UserReadSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['username','first_name','last_name','password']   

