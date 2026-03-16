from time import timezone
from django.contrib import admin
from .models import Item
from utils.admin_helpers import cloudinary_thumbnail

# Register your models here.

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('image_thumbnail', 'title', 'category', 'status', 'reported_at', 'claimed_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'description', 'claimed_by_name')
    actions = ['mark_as_claimed']

    def mark_as_claimed(self, request, queryset):
        queryset.update(status='claimed', claimed_at=timezone.now())
    mark_as_claimed.short_description = "Mark selected items as claimed"
    
    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.image)
    image_thumbnail.short_description = 'Image'
    
