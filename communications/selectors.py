from django.db import models
from django.utils import timezone
from .models import Announcement, PrayerSchedule, DonationCampaign

def get_active_announcements():
    # Return announcements that are active and not expired.
    now = timezone.now()
    qs = Announcement.objects.filter(
        is_active=True,
        publish_at__lte=now
    ).filter(
        models.Q(expire_at__isnull=True) | models.Q(expire_at__gte=now)
    )
    return qs

def get_pinned_announcements():
    return get_active_announcements().filter(is_pinned=True)

def get_today_prayer_schedule():
    # Return today's prayer schedule if exists, else the most recent active one.
    today = timezone.now().date()
    schedule = PrayerSchedule.objects.filter(date=today).first()
    if not schedule:
        schedule = PrayerSchedule.objects.filter(is_active=True).order_by('-date').first()
    return schedule

def get_next_prayer():
    """
    Calculate the next prayer based on current time and today's schedule.
    Returns a dict with prayer name, adhan, iqama, or None if no schedule.
    """
    schedule = get_today_prayer_schedule()
    if not schedule:
        return None

    now = timezone.now().time()
    prayers = [
        ('Fajr', schedule.fajr_adhan, schedule.fajr_iqama),
        ('Dhuhr', schedule.dhuhr_adhan, schedule.dhuhr_iqama),
        ('Asr', schedule.asr_adhan, schedule.asr_iqama),
        ('Maghrib', schedule.maghrib_adhan, schedule.maghrib_iqama),
        ('Isha', schedule.isha_adhan, schedule.isha_iqama),
    ]

    for name, adhan, iqama in prayers:
        if now < adhan:
            return {'name': name, 'adhan': adhan, 'iqama': iqama}

    # If past Isha, next is tomorrow's Fajr (I'll handle in view with fallback)
    return {'name': 'Fajr (tomorrow)', 'adhan': prayers[0][1], 'iqama': prayers[0][2]}

def get_active_donation_campaigns():
    return DonationCampaign.objects.filter(is_active=True).order_by('-created_at')

def get_mosque_info():
    from .models import MosqueInfo
    return MosqueInfo.objects.first()  # There should be only one

def get_active_mosque_rules():
    from .models import MosqueRule
    return MosqueRule.objects.filter(is_active=True)