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
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
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