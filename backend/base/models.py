from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class AbstractBaseModel(models.Model):
    """
    Base model providing standard timestamp fields for audit tracking.
    """
    created_at = models.DateTimeField(auto_now_add=True, help_text=_("Record creation timestamp"),null=True,blank=True)
    updated_at = models.DateTimeField(auto_now=True, help_text=_("Record last update timestamp"),null=True,blank=True)

    class Meta:
        abstract = True