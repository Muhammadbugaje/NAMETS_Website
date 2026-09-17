from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import Event
from django.core.cache import cache

@receiver(post_save, sender=Event)
@receiver(post_delete, sender=Event)
def event_changed(sender, instance, **kwargs):
    cache.delete('hp_featured_event')
    cache.delete('hp_upcoming_events')