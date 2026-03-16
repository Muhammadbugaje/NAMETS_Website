from django import forms
from .models import Subscriber

class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscriber
        fields = ['email', 'notify_announcements', 'notify_events', 'notify_prayer_changes']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'Your email address'}),
        }
        labels = {
            'notify_announcements': 'New announcements',
            'notify_events': 'Upcoming events',
            'notify_prayer_changes': 'Prayer time changes',
        }