from django.db import models
from django.conf import settings


class Message(models.Model):
    """A message sent by a user to one or many recipients."""

    TARGET_DIRECT   = 'direct'
    TARGET_OFFICES  = 'offices'
    TARGET_CURRENT  = 'current'
    TARGET_ALUMNI   = 'alumni'
    TARGET_EVERYONE = 'everyone'
    TARGET_CHOICES = [
        (TARGET_DIRECT,   'Specific people'),
        (TARGET_OFFICES,  'Specific offices'),
        (TARGET_CURRENT,  'All current members'),
        (TARGET_ALUMNI,   'All alumni'),
        (TARGET_EVERYONE, 'Everyone'),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    target_label = models.CharField(max_length=200, blank=True,
                                    help_text="Human-readable summary, e.g. 'All alumni'")
    is_pinned = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-is_pinned', '-sent_at']
        indexes = [
            models.Index(fields=['-sent_at']),
            models.Index(fields=['sender', '-sent_at']),
        ]

    def __str__(self):
        return f"{self.sender} → {self.target_label}: {self.subject}"

    @property
    def recipient_count(self):
        return self.recipients.count()

    @property
    def read_count(self):
        return self.recipients.filter(is_read=True).count()

    @property
    def target_icon(self):
        return {
            self.TARGET_DIRECT:   'fa-user',
            self.TARGET_OFFICES:  'fa-building',
            self.TARGET_CURRENT:  'fa-users',
            self.TARGET_ALUMNI:   'fa-graduation-cap',
            self.TARGET_EVERYONE: 'fa-globe',
        }.get(self.target_type, 'fa-envelope')


class MessageRecipient(models.Model):
    """Per-user copy of a message with read/delete state."""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name='recipients'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='received_messages',
    )
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    delivered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')
        ordering = ['-message__is_pinned', '-message__sent_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'is_deleted']),
        ]

    def __str__(self):
        return f"{self.user} ← {self.message.subject}"