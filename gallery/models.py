from django.db import models
from django.utils import timezone
from cloudinary.models import CloudinaryField

# Create your models here.

class Gallery(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField(default=timezone.now)
    cover_image = CloudinaryField('image',folder='gallery', blank=True, null=True, help_text="Optional cover image")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name_plural = "Galleries"

    def __str__(self):
        return self.title

class GalleryImage(models.Model):
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name='images')
    image = CloudinaryField('image', folder='gallery', blank=True, null=True)
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image for {self.gallery.title}"