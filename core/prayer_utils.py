# core/prayer_utils.py
from datetime import datetime, timedelta
from django.utils import timezone
import requests

# Use your existing selector
from communications.selectors import get_today_prayer_schedule

def get_today_prayer_times_from_db():
    """Return a dict of prayer times (adhan) from today's PrayerSchedule"""
    schedule = get_today_prayer_schedule()
    if not schedule:
        return None
    return {
        "Fajr": schedule.fajr_adhan,
        "Dhuhr": schedule.dhuhr_adhan,
        "Asr": schedule.asr_adhan,
        "Maghrib": schedule.maghrib_adhan,
        "Isha": schedule.isha_adhan,
    }

def get_next_prayer_countdown(prayer_times_dict):
    """Calculate next prayer name and remaining time as timedelta"""
    if not prayer_times_dict:
        return None, None
    now = timezone.localtime(timezone.now()).time()
    prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    for prayer in prayers:
        prayer_time = prayer_times_dict.get(prayer)
        if prayer_time and prayer_time > now:
            diff = datetime.combine(datetime.today(), prayer_time) - datetime.combine(datetime.today(), now)
            return prayer, diff
    # If all prayers passed, next is Fajr tomorrow
    tomorrow_fajr = prayer_times_dict.get("Fajr")
    if tomorrow_fajr:
        diff = (datetime.combine(datetime.today() + timedelta(days=1), tomorrow_fajr) - 
                datetime.combine(datetime.today(), now))
        return "Fajr (tomorrow)", diff
    return None, None

def format_countdown(td):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if not parts and seconds > 0:
        parts.append(f"{seconds}s")
    return " ".join(parts)

def get_hijri_date():
    """Fetch only Hijri date from Aladhan API"""
    today = datetime.now().strftime("%d-%m-%Y")
    url = f"http://api.aladhan.com/v1/gToH/{today}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("code") == 200:
            hijri = data["data"]["hijri"]
            return f"{hijri['day']} {hijri['month']['en']} {hijri['year']}"
    except Exception as e:
        print(f"Hijri API error: {e}")
    return None