from django import forms

class SubscriptionForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Your email address'})
    )
    notify_announcements = forms.BooleanField(
        required=False, 
        label='New announcements'
    )
    notify_events = forms.BooleanField(
        required=False, 
        label='Upcoming events'
    )
    notify_prayer_changes = forms.BooleanField(
        required=False, 
        label='Prayer time changes'
    )
