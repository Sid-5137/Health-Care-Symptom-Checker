from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    family_history = models.TextField(blank=True, null=True)
    # Add more fields as needed

class SymptomHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    symptoms = models.TextField()
    probable_conditions = models.TextField()
    recommendations = models.TextField()
    disclaimer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
