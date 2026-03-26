from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Gallery

@receiver(post_save, sender=Gallery)
@receiver(post_delete, sender=Gallery)
def gallery_changed(sender, instance, **kwargs):
    cache.delete('hp_gallery')