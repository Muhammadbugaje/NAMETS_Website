from django.db import models
from django.utils import timezone
from .models import Announcement, PrayerSchedule, DonationCampaign


def get_active_announcements():
    now = timezone.now()
    return Announcement.objects.filter(
        is_active=True,
        publish_at__lte=now
    ).filter(
        models.Q(expire_at__isnull=True) | models.Q(expire_at__gte=now)
    )


def get_pinned_announcements():
    return get_active_announcements().filter(is_pinned=True)


def get_today_prayer_schedule():
    today = timezone.localdate()                                    # ← FIXED
    schedule = PrayerSchedule.objects.filter(date=today).first()
    if not schedule:
        schedule = PrayerSchedule.objects.filter(
            is_active=True
        ).order_by('-date').first()
    return schedule


def get_next_prayer():
    schedule = get_today_prayer_schedule()
    if not schedule:
        return None

    now = timezone.localtime().time()                             

    prayers = [
        ('Fajr',    schedule.fajr_adhan,    schedule.fajr_iqama),
        ('Dhuhr',   schedule.dhuhr_adhan,   schedule.dhuhr_iqama),
        ('Asr',     schedule.asr_adhan,     schedule.asr_iqama),
        ('Maghrib', schedule.maghrib_adhan, schedule.maghrib_iqama),
        ('Isha',    schedule.isha_adhan,    schedule.isha_iqama),
    ]

    for name, adhan, iqama in prayers:
        if now < adhan:
            return {'name': name, 'adhan': adhan, 'iqama': iqama}

    return {'name': 'Fajr (tomorrow)', 'adhan': prayers[0][1], 'iqama': prayers[0][2]}


def get_active_donation_campaigns():
    return DonationCampaign.objects.filter(is_active=True).order_by('-created_at')


def get_mosque_info():
    from .models import MosqueInfo
    return MosqueInfo.objects.first()


def get_active_mosque_rules():
    from .models import MosqueRule
    return MosqueRule.objects.filter(is_active=True)