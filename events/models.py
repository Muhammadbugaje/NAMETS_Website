from django.db import models
from django.utils import timezone
from cloudinary.models import CloudinaryField

# Create your models here.

class EventCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Event categories"

    def __str__(self):
        return self.name


class Event(models.Model):
    HERO_LAYOUT_CHOICES = [
        ('overlay', 'Text overlaid on image'),
        ('separate', 'Image separate from text'),
    ]
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True) 
    category = models.ForeignKey(EventCategory, on_delete=models.SET_NULL, null=True, blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    location = models.CharField(max_length=200)
    image = CloudinaryField('image', folder='events', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    send_email = models.BooleanField(
        default=False,
        help_text="Send email notification when this event is created?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    hero_layout = models.CharField(
        max_length=10,
        choices=HERO_LAYOUT_CHOICES,
        default='overlay',
        help_text="'Overlay' puts text on the image; 'Separate' shows image above text."
    )

    class Meta:
        ordering = ['start_datetime']

    def __str__(self):
        return self.title

    @property
    def status(self):
        if not self.start_datetime or not self.end_datetime:
            return "draft"
        now = timezone.now()
        if now < self.start_datetime:
            return "upcoming"
        elif now > self.end_datetime:
            return "past"
        else:
            return "ongoing"
        
        

class EventLink(models.Model):
    LINK_TYPES = [
        ('zoom', 'Zoom Meeting'),
        ('google_meet', 'Google Meet'),
        ('youtube', 'YouTube Live'),
        ('instagram', 'Instagram Live'),
        ('facebook', 'Facebook Live'),
        ('whatsapp', 'WhatsApp Group/Channel'),
        ('website', 'Website / Registration'),
        ('pdf', 'PDF Document'),
        ('drive', 'Google Drive'),
        ('other', 'Other Link'),
    ]

    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='links'
    )
    url = models.URLField(max_length=500)
    link_type = models.CharField(max_length=20, choices=LINK_TYPES, default='other')
    description = models.CharField(max_length=200, blank=True, help_text="Optional description")
    is_primary = models.BooleanField(default=False, help_text="Mark as the main link for this event")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'link_type']

    def __str__(self):
        return f"{self.get_link_type_display()}: {self.url[:50]}"

    def get_icon(self):
        icons = {
            'zoom': 'fa-video',
            'google_meet': 'fa-google',
            'youtube': 'fa-youtube',
            'instagram': 'fa-instagram',
            'facebook': 'fa-facebook',
            'whatsapp': 'fa-whatsapp',
            'website': 'fa-globe',
            'pdf': 'fa-file-pdf',
            'drive': 'fa-google-drive',
            'other': 'fa-link',
        }
        return icons.get(self.link_type, 'fa-link')

    def get_color(self):
        colors = {
            'zoom': '#2D8CFF',
            'google_meet': '#34A853',
            'youtube': '#FF0000',
            'instagram': '#E4405F',
            'facebook': '#1877F2',
            'whatsapp': '#25D366',
            'website': '#0F3D2E',
            'pdf': '#E53E3E',
            'drive': '#4285F4',
            'other': '#718096',
        }
        return colors.get(self.link_type, '#718096')



        