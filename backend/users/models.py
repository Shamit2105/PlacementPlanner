from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    middle_name = models.CharField(max_length=255, null=True, blank=True)

    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email
    
class UserProfile(models.Model):
    user = models.OneToOneField(User,on_delete=models.CASCADE,related_name='profile')
    bio  = models.TextField(blank=True,max_length=500)
    
    def __str__(self):
        return f"Profile for {self.user.email}"