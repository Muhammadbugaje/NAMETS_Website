from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Event
from core.services.webhooks import send_webhook
from communications.models import Subscriber
from community.models import Patron

@receiver(post_save, sender=Event)
def event_saved_handler(sender, instance, created, **kwargs):
    if not created or not instance.send_email:
        return

    # Gather recipients
    subscribers = Subscriber.objects.filter(
        is_active=True,
        notify_events=True
    ).values_list('email', flat=True)
    patrons = Patron.objects.filter(is_active=True).exclude(email='').values_list('email', flat=True)
    recipients = list(subscribers) + list(patrons)

    if not recipients:
        return

    # Flattened payload
    payload = {
        'recipients': recipients,
        'title': instance.title,
        'description': instance.description,
        'start_datetime': instance.start_datetime.isoformat(),
        'end_datetime': instance.end_datetime.isoformat() if instance.end_datetime else None,
        'location': instance.location,
    }

    send_webhook('event_created', payload)