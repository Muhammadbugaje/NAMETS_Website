from unfold.admin import ModelAdmin, TabularInline
from django.contrib import admin
from .models import EventCategory, Event
from utils.admin_helpers import cloudinary_thumbnail
from django.urls import reverse
from django.utils.html import format_html
# Register your models here.

@admin.register(EventCategory)
class EventCategoryAdmin(ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name',)

@admin.register(Event)
class EventAdmin(ModelAdmin):
    list_display = ('image_thumbnail', 'title', 'category', 'start_datetime', 'end_datetime', 'status', 'is_featured', 'is_active','preview_button')
    list_filter = ('category', 'is_featured', 'is_active')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'start_datetime'
    readonly_fields = ('status','preview_button',)  # just for display in admin, though it's a property but calculated by time automatically   
    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.image)
    image_thumbnail.short_description = 'Image'
    
    def preview_button(self, obj):
        if obj and obj.pk:
            url = reverse('events:detail', args=[obj.slug])
            return format_html('<a href="{}" target="_blank" class="button">Preview</a>', url)
        return "—"
    preview_button.short_description = 'Preview'