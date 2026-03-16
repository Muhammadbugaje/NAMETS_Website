# communications/serializers.py
from rest_framework import serializers
from .models import Subscriber, Announcement

class SubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber
        fields = ['id', 'email', 'phone', 'notify_announcements', 'notify_events', 'notify_prayer_changes', 'is_active']
        

class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'publish_at', 'expire_at', 'category']