from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from .models import Subscriber, Announcement
from .serializers import SubscriberSerializer, AnnouncementSerializer
from django.utils import timezone
from datetime import timedelta
from utils.auth import N8NAuthentication


@api_view(['GET'])
@authentication_classes([N8NAuthentication])
@permission_classes([])
def get_subscribers(request):
    # Optionally filter by preferences via query params
    pref_announcements = request.GET.get('announcements')
    pref_events = request.GET.get('events')
    pref_prayer = request.GET.get('prayer')
    qs = Subscriber.objects.filter(is_active=True)
    if pref_announcements:
        qs = qs.filter(notify_announcements=True)
    if pref_events:
        qs = qs.filter(notify_events=True)
    if pref_prayer:
        qs = qs.filter(notify_prayer_changes=True)
    serializer = SubscriberSerializer(qs, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@authentication_classes([N8NAuthentication])
@permission_classes([])
def new_announcements(request):
    # Return announcements published since a given timestamp
    since = request.GET.get('since')
    if since:
        try:
            since = timezone.datetime.fromisoformat(since)
        except:
            since = timezone.now() - timedelta(days=1)
    else:
        since = timezone.now() - timedelta(days=1)
    qs = Announcement.objects.filter(publish_at__gte=since, is_active=True)
    serializer = AnnouncementSerializer(qs, many=True)
    return Response(serializer.data)



@api_view(['POST'])
@authentication_classes([N8NAuthentication])
@permission_classes([])
def send_custom_message(request):
    # Expects JSON with: recipients (list of emails/phones), subject, body, channel (email/whatsapp)
    data = request.data
    # You can log the request or forward to n8n via another webhook if needed.
    # I will implement this later (Muhammad Bugaje)