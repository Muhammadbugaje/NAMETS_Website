from django.contrib import admin
from .models import Gallery, GalleryImage
from utils.admin_helpers import cloudinary_thumbnail

class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 1  # shows one empty row by default

@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('image_thumbnail', 'title', 'date', 'created_at')
    list_filter = ('date',)
    search_fields = ('title', 'description')
    inlines = [GalleryImageInline]
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'date', 'cover_image')
        }),
    )
    
    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.image)
    image_thumbnail.short_description = 'Image'