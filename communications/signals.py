from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Announcement, Subscriber, PrayerSchedule
from core.services.webhooks import send_webhook
from community.models import Patron

from events.models import Event
from communications.models import Subscriber


@receiver(post_save, sender=Announcement)
def announcement_saved_handler(sender, instance, created, **kwargs):
    if not created or not instance.send_email:
        return

    subscribers = Subscriber.objects.filter(
        is_active=True,
        notify_announcements=True
    ).values_list('email', flat=True)
    patrons = Patron.objects.filter(is_active=True).exclude(email='').values_list('email', flat=True)
    recipients = list(subscribers) + list(patrons)

    if not recipients:
        return

    payload = {
        'recipients': recipients,
        'title': instance.title,
        'content': instance.content,
        'publish_at': instance.publish_at.isoformat(),
    }

    send_webhook('announcement_created', payload)

# -------------------- Subscriber --------------------
@receiver(post_save, sender=Subscriber)
def subscriber_saved_handler(sender, instance, created, **kwargs):
    if created:
        payload = {
            'recipients': [instance.email],
            'email': instance.email,
            'preferences': {
                'announcements': instance.notify_announcements,
                'events': instance.notify_events,
                'prayer': instance.notify_prayer_changes,
            }
        }
        send_webhook('subscriber_joined', payload)

@receiver(post_delete, sender=Subscriber)
def subscriber_deleted_handler(sender, instance, **kwargs):
    payload = {
        'recipients': [instance.email],
        'email': instance.email,
    }
    send_webhook('subscriber_unsubscribed', payload)

# -------------------- PrayerSchedule --------------------
@receiver(post_save, sender=PrayerSchedule)
def prayer_saved_handler(sender, instance, created, **kwargs):
    if not instance.send_email:
        return
    subscribers = Subscriber.objects.filter(is_active=True, notify_prayer_changes=True).values_list('email', flat=True)
    patrons = Patron.objects.filter(is_active=True).exclude(email='').values_list('email', flat=True)
    recipients = list(subscribers) + list(patrons)
    if not recipients:
        return
    payload = {
        'recipients': recipients,
        'date': instance.date.isoformat(),
        'fajr_adhan': str(instance.fajr_adhan),
        'fajr_iqama': str(instance.fajr_iqama),
        'dhuhr_adhan': str(instance.dhuhr_adhan),
        'dhuhr_iqama': str(instance.dhuhr_iqama),
        'asr_adhan': str(instance.asr_adhan),
        'asr_iqama': str(instance.asr_iqama),
        'maghrib_adhan': str(instance.maghrib_adhan),
        'maghrib_iqama': str(instance.maghrib_iqama),
        'isha_adhan': str(instance.isha_adhan),
        'isha_iqama': str(instance.isha_iqama),
    }
    send_webhook('prayer_updated', payload)

@receiver(post_save, sender=Event)
def event_saved_handler(sender, instance, created, **kwargs):
    if not created or not instance.send_email:
        return

    subscribers = Subscriber.objects.filter(
        is_active=True,
        notify_events=True
    ).values_list('email', flat=True)

    patrons = Patron.objects.filter(
        is_active=True
    ).exclude(email='').values_list('email', flat=True)

    recipients = list(subscribers) + list(patrons)

    if not recipients:
        return

    # Flat structure — matches n8n Prep: event_created
    send_webhook('event_created', {
        'recipients': recipients,
        'title': instance.title,
        'description': instance.description,
        'start_datetime': instance.start_datetime.isoformat(),
        'end_datetime': instance.end_datetime.isoformat() if instance.end_datetime else None,
        'location': instance.location,
    })