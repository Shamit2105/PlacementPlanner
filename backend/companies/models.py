from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from base.models import AbstractBaseModel

class Company(AbstractBaseModel):
    name = models.CharField(max_length=255, unique=True, help_text=_("Company Name"))
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    ai_trend_analysis = models.JSONField(blank=True,null=True)
    
    class Meta:
        db_table = 'pr_company'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class PlacementExperience(AbstractBaseModel):
    ROUND_CHOICES = [
        ('OA', 'Online Assessment'),
        ('INTERVIEW', 'Technical/HR Interview')
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="experiences")
    round_type = models.CharField(max_length=20, choices=ROUND_CHOICES)
    target_role = models.CharField(max_length=100, default="Software Engineer")
    batch_year = models.IntegerField(null=True, blank=True)
    
    source_platform = models.CharField(max_length=100) 
    source_url = models.URLField(unique=True) 
    raw_text = models.TextField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)

    extracted_dsa_questions = models.JSONField(default=list, blank=True)
    extracted_core_topics = models.JSONField(default=list, blank=True)
    
    is_vectorized = models.BooleanField(default=False)
    is_extracted = models.BooleanField(default=False)

    class Meta:
        db_table = 'pr_placement_experience'

    def __str__(self):
        return f"{self.company.name} - {self.get_round_type_display()}"