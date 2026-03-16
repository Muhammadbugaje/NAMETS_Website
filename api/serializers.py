from rest_framework import serializers
from communications.models import Announcement, Subscriber
from events.models import Event

class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'publish_at']

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['id', 'title', 'description', 'start_datetime', 'end_datetime', 'location']

class SubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber
        fields = ['id', 'email', 'notify_announcements', 'notify_events', 'notify_prayer_changes']