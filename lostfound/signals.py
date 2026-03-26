from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Item

@receiver(post_save, sender=Item)
@receiver(post_delete, sender=Item)
def item_changed(sender, instance, **kwargs):
    cache.delete('hp_lost_found')