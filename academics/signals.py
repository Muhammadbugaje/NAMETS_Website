from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Session 

@receiver(post_save, sender=Session)
@receiver(post_delete, sender=Session)
def session_changed(sender, instance, **kwargs):
    cache.delete('hp_sessions')