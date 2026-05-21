from django.db import models
from django.utils.text import slugify

class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            original_slug = slugify(self.name)
            unique_slug = original_slug
            num = 1
            while Company.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{original_slug}-{num}"
                num += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class PlacementExperience(models.Model):
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
    raw_text = models.TextField(null=True,blank=True)
    content_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)

    extracted_dsa_questions = models.JSONField(default=list, blank=True)
    extracted_core_topics = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    is_vectorized = models.BooleanField(default=False)
    is_extracted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company.name} - {self.get_round_type_display()} ({self.batch_year})"