from django.db import models
from django.utils import timezone
from cloudinary.models import CloudinaryField

# Create your models here.

class Item(models.Model):
    STATUS_CHOICES = [
        ('lost', 'Lost'),
        ('found', 'Found'),
        ('claimed', 'Claimed'),
    ]
    CATEGORY_CHOICES = [
        ('electronics', 'Electronics'),
        ('clothing', 'Clothing'),
        ('watches', 'Watches'),
        ('caps', 'Caps'),
        ('accessories', 'Accessories'),
        ('books', 'Books'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    image = CloudinaryField('image',folder='lostfound', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='lost')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    reported_at = models.DateTimeField(auto_now_add=True)
    claimed_by_name = models.CharField(max_length=100, blank=True)
    claimed_by_contact = models.CharField(max_length=100, blank=True)
    claimed_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-reported_at']

    def __str__(self):
        return f"{self.get_status_display()}: {self.title}"

    def save(self, *args, **kwargs):
        if self.status == 'claimed' and not self.claimed_at:
            self.claimed_at = timezone.now()
        super().save(*args, **kwargs)