from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Announcement, DonationCampaign, Subscriber, PrayerSchedule
from core.email_utils import send_templated_email
from community.models import Patron
from django.core.cache import cache
from events.models import Event



# ==================== EMAIL NOTIFICATIONS (templated, branded) ====================

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

    send_templated_email(
        subject=f"New Announcement: {instance.title}",
        recipients=recipients,
        template_name='emails/announcement.html',
        context={
            'announcement': instance,
            'announcement_url': f"/communications/announcements/{instance.slug}/",
        },
    )



@receiver(post_save, sender=Subscriber, dispatch_uid="communications_subscriber_welcome_email")
def subscriber_saved_handler(sender, instance, created, **kwargs):
    if created:
        print(f"✅ SIGNAL FIRED for {instance.email}")
        send_templated_email(
            subject="Assalamu Alaikum – Welcome to NAMETS Updates!",
            recipients=[instance.email],
            template_name='emails/welcome.html',
            context={
                'preferences': {
                    'notify_announcements': instance.notify_announcements,
                    'notify_events': instance.notify_events,
                    'notify_prayer_changes': instance.notify_prayer_changes,
                },
            },
        )

@receiver(post_save, sender=PrayerSchedule)
def prayer_saved_handler(sender, instance, created, **kwargs):
    if not instance.send_email:
        return
    subscribers = Subscriber.objects.filter(is_active=True, notify_prayer_changes=True).values_list('email', flat=True)
    patrons = Patron.objects.filter(is_active=True).exclude(email='').values_list('email', flat=True)
    recipients = list(subscribers) + list(patrons)
    if not recipients:
        return

    send_templated_email(
        subject=f"Prayer Time Update – {instance.date.isoformat()}",
        recipients=recipients,
        template_name='emails/prayer_update.html',
        context={
            'date': instance.date,
            'prayers': [
                {'label': '🌙 Fajr', 'adhan': instance.fajr_adhan, 'iqama': instance.fajr_iqama},
                {'label': '☀️ Dhuhr', 'adhan': instance.dhuhr_adhan, 'iqama': instance.dhuhr_iqama},
                {'label': '🌤️ Asr', 'adhan': instance.asr_adhan, 'iqama': instance.asr_iqama},
                {'label': '🌇 Maghrib', 'adhan': instance.maghrib_adhan, 'iqama': instance.maghrib_iqama},
                {'label': '🌙 Isha', 'adhan': instance.isha_adhan, 'iqama': instance.isha_iqama},
            ],
        },
    )


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

    send_templated_email(
        subject=f"Upcoming Event: {instance.title}",
        recipients=recipients,
        template_name='emails/event.html',
        context={
            'event': instance,
            'event_url': f"/events/{instance.slug}/",
            'calendar_url': f"/events/{instance.slug}/calendar.ics",
        },
    )


# ==================== CACHE INVALIDATION ====================

@receiver(post_save, sender=Announcement)
@receiver(post_delete, sender=Announcement)
def announcement_cache_invalidator(sender, instance, **kwargs):
    cache.delete('hp_announcements')


@receiver(post_save, sender=PrayerSchedule)
@receiver(post_delete, sender=PrayerSchedule)
def prayer_cache_invalidator(sender, instance, **kwargs):
    cache.delete('hp_prayer')


@receiver(post_save, sender=DonationCampaign)
@receiver(post_delete, sender=DonationCampaign)
def campaign_cache_invalidator(sender, instance, **kwargs):
    cache.delete('hp_campaigns')