from django.contrib import admin
from .models import Gallery, GalleryImage
from utils.admin_helpers import cloudinary_thumbnail   # make sure this helper exists

class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 1
    fields = ('image' , 'image_thumbnail', 'caption', 'order')
    readonly_fields = ('image_thumbnail',)

    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.image)
    image_thumbnail.short_description = 'Thumbnail'


@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'created_at', 'cover_image_thumbnail')
    list_filter = ('date',)
    search_fields = ('title', 'description')
    inlines = [GalleryImageInline]

    def cover_image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.cover_image)
    cover_image_thumbnail.short_description = 'Cover Image'