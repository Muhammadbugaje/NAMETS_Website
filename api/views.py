from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from communications.models import Announcement, Subscriber
from events.models import Event
from .serializers import AnnouncementSerializer, EventSerializer, SubscriberSerializer

@api_view(['GET'])
def get_subscribers(request):
    """Return active subscribers, optionally filtered by notification preferences."""
    qs = Subscriber.objects.filter(is_active=True)
    if request.GET.get('announcements'):
        qs = qs.filter(notify_announcements=True)
    if request.GET.get('events'):
        qs = qs.filter(notify_events=True)
    if request.GET.get('prayer'):
        qs = qs.filter(notify_prayer_changes=True)
    serializer = SubscriberSerializer(qs, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def new_announcements(request):
    """Return announcements published after a given timestamp."""
    since = request.GET.get('since')
    if since:
        try:
            since = timezone.datetime.fromisoformat(since.replace('Z', '+00:00'))
        except:
            since = timezone.now() - timedelta(days=1)
    else:
        since = timezone.now() - timedelta(days=1)
    qs = Announcement.objects.filter(publish_at__gte=since, is_active=True)
    serializer = AnnouncementSerializer(qs, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def upcoming_events(request):
    """Return events starting within the next N days."""
    days = int(request.GET.get('days', 7))
    now = timezone.now()
    end = now + timedelta(days=days)
    qs = Event.objects.filter(start_datetime__gte=now, start_datetime__lte=end, is_active=True)
    serializer = EventSerializer(qs, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def today_prayer(request):
    """Return today's prayer schedule (mock for now)."""
    # If you have a PrayerSchedule model, implement properly.
    # For now, return dummy data.
    from datetime import date
    return Response({
        'date': date.today(),
        'fajr': '05:30',
        'dhuhr': '12:45',
        'asr': '16:00',
        'maghrib': '18:15',
        'isha': '19:45'
    })