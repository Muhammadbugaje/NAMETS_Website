from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Patron, Developer

@receiver(post_save, sender=Patron)
@receiver(post_delete, sender=Patron)
def patron_changed(sender, instance, **kwargs):
    cache.delete('hp_patron')

@receiver(post_save, sender=Developer)
@receiver(post_delete, sender=Developer)
def developer_changed(sender, instance, **kwargs):
    cache.delete('hp_developers')