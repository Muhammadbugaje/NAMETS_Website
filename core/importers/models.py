import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class PendingImportBatch(models.Model):
    """A validated-but-not-yet-committed upload, waiting for the person to
    click Confirm. Expires on its own — see clean_expired() below — so a
    review screen that's abandoned doesn't leave data around forever.
    """

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    import_key = models.CharField(max_length=50)  # matches an IMPORT_REGISTRY key
    valid_rows = models.JSONField(default=list)  # [{'row_number': 2, 'data': {...}}, ...]
    extra_data = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=30)

    @classmethod
    def clean_expired(cls):
        """Call this from a scheduled task or simply on every upload_review() call."""
        cutoff = timezone.now() - timedelta(minutes=30)
        cls.objects.filter(created_at__lt=cutoff).delete()