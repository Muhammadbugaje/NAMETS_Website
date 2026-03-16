from django.contrib import admin
from .models import EventCategory, Event
from utils.admin_helpers import cloudinary_thumbnail

# Register your models here.

@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name',)

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('image_thumbnail', 'title', 'category', 'start_datetime', 'end_datetime', 'status', 'is_featured', 'is_active')
    list_filter = ('category', 'is_featured', 'is_active')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'start_datetime'
    readonly_fields = ('status',)  # just for display in admin, though it's a property but calculated by time automatically
        
    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.image)
    image_thumbnail.short_description = 'Image'