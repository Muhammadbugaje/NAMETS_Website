import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'namets.settings')
django.setup()

from django.test import Client
from communications.models import Subscriber

# Ensure subscriber exists with different prefs
count_before = Subscriber.objects.filter(email__iexact='test@example.com').count()
print('subscriber count before:', count_before)
sub, _ = Subscriber.objects.get_or_create(
    email='test@example.com',
    defaults={'token': '00000000-0000-0000-0000-000000000000', 'is_active': True},
)
sub.notify_announcements = True
sub.notify_events = True
sub.notify_prayer_changes = False
sub.save()

fresh = Subscriber.objects.get(email__iexact='test@example.com')
print('subscriber prefs after save (fresh fetch)', fresh.notify_announcements, fresh.notify_events, fresh.notify_prayer_changes)

count_after = Subscriber.objects.filter(email__iexact='test@example.com').count()
print('subscriber count after:', count_after)

client = Client()
print('subscriber prefs before post', sub.notify_announcements, sub.notify_events, sub.notify_prayer_changes)

# mimic how subscribe view builds new_prefs
new_prefs = {
    'notify_announcements': 'notify_announcements' in {'email': 'test@example.com', 'notify_announcements': 'on'},
    'notify_events': 'notify_events' in {'email': 'test@example.com', 'notify_announcements': 'on'},
    'notify_prayer_changes': 'notify_prayer_changes' in {'email': 'test@example.com', 'notify_announcements': 'on'},
}
print('mimicked new_prefs', new_prefs)
current_prefs = {
    'notify_announcements': sub.notify_announcements,
    'notify_events': sub.notify_events,
    'notify_prayer_changes': sub.notify_prayer_changes,
}
print('current_prefs', current_prefs)
print('prefs equal?', current_prefs == new_prefs)

resp = client.post('/communications/subscribe/', {'email': 'test@example.com', 'notify_announcements': 'on'}, follow=False)
print('status', resp.status_code)
print('redirect', resp.get('Location'))
print('session pending_subscription', dict(client.session).get('pending_subscription'))
