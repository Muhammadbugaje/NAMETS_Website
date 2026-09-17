from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()
from django.utils import timezone


class Notification(models.Model):

    class Type(models.TextChoices):
        # --- Content ---
        ANNOUNCEMENT = "announcement", "📢 Announcement"
        EVENT        = "event",        "📅 Event"
        MEMBERSHIP   = "membership",   "🙋 Membership Application"
        TUTOR_APP    = "tutor_app",    "👨‍🏫 Tutor Application"
        ISLAMIYYA    = "islamiyya",    "📖 Islamiyyah Registration"
        LOST_FOUND   = "lostfound",    "🔍 Lost & Found"
        QA           = "qa",           "❓ Q&A Question"
        GALLERY      = "gallery",      "🖼 Gallery"
        GENERAL      = "general",      "ℹ General"

        # --- Governance ---
        TASK         = "task",         "✅ Task"
        PROPOSAL     = "proposal",     "🗳 Proposal"
        VOTE         = "vote",         "🗳 Vote cast"
        NOMINATION   = "nomination",   "🕌 Nomination"
        OATH         = "oath",         "🤝 Oath"
        HANDOVER     = "handover",     "🎓 Handover"
        GOVERNANCE   = "governance",   "🏛 Governance"

        # --- Business ---
        SHOP_ORDER   = "shop_order",   "🛍 Shop Order"
        BOOKING      = "booking",      "🎟 Booking"
        FREE_CLAIM   = "free_claim",   "🎁 Free Claim"
        FORM_PURCHASE= "form_purchase","📄 Form Purchase"
        EQUIPMENT    = "equipment",    "🔧 Equipment"

        # --- Academics ---
        CBT          = "cbt",          "🧠 CBT"
        RESOURCE     = "resource",     "📚 Resource"

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
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["-created_at"]),
        ]

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
            # Content
            "announcement": "campaign",
            "event":        "event",
            "membership":   "how_to_reg",
            "tutor_app":    "person_add",
            "islamiyya":    "auto_stories",
            "lostfound":    "find_in_page",
            "qa":           "quiz",
            "gallery":      "photo_library",
            "general":      "info",
            # Governance
            "task":         "check_circle",
            "proposal":     "how_to_vote",
            "vote":         "ballot",
            "nomination":   "workspace_premium",
            "oath":         "handshake",
            "handover":     "school",
            "governance":   "account_balance",
            # Business
            "shop_order":   "shopping_bag",
            "booking":      "confirmation_number",
            "free_claim":   "redeem",
            "form_purchase":"description",
            "equipment":    "build",
            # Academics
            "cbt":          "psychology",
            "resource":     "library_books",
        }.get(self.notification_type, "notifications")

    @property
    def color_class(self):
        return {
            # Content
            "announcement": "green",
            "event":        "blue",
            "membership":   "purple",
            "tutor_app":    "purple",
            "islamiyya":    "gold",
            "lostfound":    "red",
            "qa":           "teal",
            "gallery":      "pink",
            "general":      "gray",
            # Governance
            "task":         "gold",
            "proposal":     "blue",
            "vote":         "blue",
            "nomination":   "purple",
            "oath":         "green",
            "handover":     "green",
            "governance":   "gold",
            # Business
            "shop_order":   "green",
            "booking":      "blue",
            "free_claim":   "gold",
            "form_purchase":"green",
            "equipment":    "blue",
            # Academics
            "cbt":          "purple",
            "resource":     "teal",
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