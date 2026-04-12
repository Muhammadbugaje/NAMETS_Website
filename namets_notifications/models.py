from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Notification(models.Model):

    class Type(models.TextChoices):
        ANNOUNCEMENT = "announcement", "📢 Announcement"
        EVENT        = "event",        "📅 Event"
        MEMBERSHIP   = "membership",   "🙋 Membership Application"
        TUTOR_APP    = "tutor_app",    "👨‍🏫 Tutor Application"
        ISLAMIYYA    = "islamiyya",    "📖 Islamiyyah Registration"
        LOST_FOUND   = "lostfound",    "🔍 Lost & Found"
        QA           = "qa",           "❓ Q&A Question"
        GALLERY      = "gallery",      "🖼 Gallery"
        GENERAL      = "general",      "ℹ General"

    recipient             = models.ForeignKey(User, on_delete=models.CASCADE, related_name="namets_notifications")
    notification_type     = models.CharField(max_length=30, choices=Type.choices, default=Type.GENERAL)
    title                 = models.CharField(max_length=255)
    message               = models.TextField()
    admin_link            = models.CharField(max_length=500, blank=True)
    is_read               = models.BooleanField(default=False)
    created_at            = models.DateTimeField(default=timezone.now)
    read_at               = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.title}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    @property
    def icon(self):
        return {
            "announcement": "campaign",
            "event":        "event",
            "membership":   "how_to_reg",
            "tutor_app":    "person_add",
            "islamiyya":    "auto_stories",
            "lostfound":    "find_in_page",
            "qa":           "quiz",
            "gallery":      "photo_library",
            "general":      "info",
        }.get(self.notification_type, "notifications")

    @property
    def color_class(self):
        return {
            "announcement": "green",
            "event":        "blue",
            "membership":   "purple",
            "tutor_app":    "purple",
            "islamiyya":    "gold",
            "lostfound":    "red",
            "qa":           "teal",
            "gallery":      "pink",
            "general":      "gray",
        }.get(self.notification_type, "gray")


class ActivityLog(models.Model):

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DELETED = "deleted", "Deleted"

    user        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="activity_logs")
    action      = models.CharField(max_length=10, choices=Action.choices)
    model_name  = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=300)
    admin_link  = models.CharField(max_length=500, blank=True)
    timestamp   = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name}"