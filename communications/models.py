from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
from ckeditor.fields import RichTextField

# subscribers models from inbuilt django user model
import uuid

# Create your models here.
User = get_user_model()

class Announcement(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('ramadan', 'Ramadan'),
        ('taaleem', 'Ta’aleem'),
        ('sale', 'Lapcoat / Sales'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = RichTextField(blank=True, null=True)
    image = CloudinaryField('image', folder='announcements', blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    is_pinned = models.BooleanField(default=False)
    publish_at = models.DateTimeField(default=timezone.now)
    expire_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    send_email = models.BooleanField(
        default=False,
        help_text="Send email notification when this event is created?"
    )
    email_sent = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-publish_at']

    def __str__(self):
        return self.title

    def is_expired(self):
        if self.expire_at and self.expire_at < timezone.now():
            return True
        return False


class PrayerSchedule(models.Model):
    date = models.DateField(unique=True)
    fajr_adhan = models.TimeField()
    fajr_iqama = models.TimeField()
    dhuhr_adhan = models.TimeField()
    dhuhr_iqama = models.TimeField()
    asr_adhan = models.TimeField()
    asr_iqama = models.TimeField()
    maghrib_adhan = models.TimeField()
    maghrib_iqama = models.TimeField()
    isha_adhan = models.TimeField()
    isha_iqama = models.TimeField()
    is_active = models.BooleanField(default=True)
    send_email = models.BooleanField(
        default=False,
        help_text="Send email notification when this event is created?"
    )

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Prayer Schedule {self.date}"


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_active = models.BooleanField(default=True)

    # Preferences
    notify_announcements = models.BooleanField(default=True)
    notify_events = models.BooleanField(default=True)
    notify_prayer_changes = models.BooleanField(default=False)  # prayer times don't change often

    # For tracking last notification sent
    last_notified = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.email

    def get_unsubscribe_url(self):
        from django.urls import reverse
        return reverse('communications:unsubscribe', args=[self.token])


class DonationCampaign(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    bank_details = models.TextField()
    goal_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
    
class MosqueInfo(models.Model):
    """General information about the Engineering Mosque."""
    location = models.CharField(max_length=200, help_text="Building/area where mosque is located")
    description = models.TextField(blank=True, help_text="Brief description or history")
    imam_name = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name_plural = "Mosque info"

    def __str__(self):
        return "Engineering Mosque Information"


class MosqueRule(models.Model):
    """Rules and guidelines for the mosque."""
    title = models.CharField(max_length=200)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title
    
class MagazineIssue(models.Model):
    title = models.CharField(max_length=200)  # e.g., "Al-Irshad Vol. 1"
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    cover_image = CloudinaryField('image', folder='magazine/covers/', blank=True, null=True)
    pdf_file = CloudinaryField('file', folder='magazine/pdfs/', blank=True, null=True)
    published_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-published_date']

    def __str__(self):
        return self.title

class Article(models.Model):
    issue = models.ForeignKey(MagazineIssue, on_delete=models.CASCADE, related_name='articles', blank=True, null=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=100, blank=True)  # e.g., "Islam & Health"
    author = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    image = CloudinaryField('image', folder='articles/', blank=True, null=True)
    published_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title
    