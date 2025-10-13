from django.contrib import admin
from .models import UserProfile, SymptomHistory

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "family_history")
    search_fields = ("user__username", "family_history")

@admin.register(SymptomHistory)
class SymptomHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    search_fields = ("user__username", "symptoms")
    list_filter = ("created_at",)
