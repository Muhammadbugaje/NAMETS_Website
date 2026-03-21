from django.contrib import admin
from .models import SiteSettings

# Register your models here.

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['tutor_applications_open', 'membership_applications_open', 'tutor_evaluations_open']
    # You can add other fields as needed