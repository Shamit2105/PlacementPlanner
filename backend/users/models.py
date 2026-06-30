from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from base.models import AbstractBaseModel
from companies.models import Question
class User(AbstractUser, AbstractBaseModel):
    middle_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(_('email address'), unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']


    def __str__(self):
        return self.email
    
class UserProfile(AbstractBaseModel):
    user = models.OneToOneField(
        to=User, on_delete=models.CASCADE, related_name='profile', help_text=_("Associated User")
    )
    bio = models.TextField(blank=True, max_length=500, help_text=_("User Biography"))
    target_role = models.CharField(max_length=100, default="Software Engineer", help_text=_("Target Placement Role"))
    batch_year = models.IntegerField(null=True, blank=True, help_text=_("Graduation Year"))
    
    questions_attempted = models.ManyToManyField(Question, related_name='users_attempted', blank=True)
    questions_passed = models.ManyToManyField(Question, related_name='users_passed', blank=True)
    questions_failed = models.ManyToManyField(Question, related_name='users_failed', blank=True)

    def __str__(self):
        return f"Profile: {self.user.email}"

