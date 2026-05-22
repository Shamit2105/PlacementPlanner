from rest_framework import serializers
from .models import Company, PlacementExperience

class CompanyResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'slug']

class PlacementExperienceResponseSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    round_type_display = serializers.CharField(source='get_round_type_display', read_only=True)

    class Meta:
        model = PlacementExperience
        fields = [
            'id', 'company_name', 'round_type', 'round_type_display',
            'target_role', 'batch_year', 'source_platform', 'source_url',
            'extracted_dsa_questions', 'extracted_core_topics', 'created_at'
        ]