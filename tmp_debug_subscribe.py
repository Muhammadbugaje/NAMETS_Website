import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'namets.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from communications.views import subscribe
from communications.models import Subscriber

# Ensure subscriber exists with different prefs
sub, _ = Subscriber.objects.get_or_create(
    email='test@example.com',
    defaults={'token': '00000000-0000-0000-0000-000000000000', 'is_active': True},
)
sub.notify_announcements = True
sub.notify_events = True
sub.notify_prayer_changes = False
sub.save()

rf = RequestFactory()
post_data = {'email': 'test@example.com', 'notify_announcements': 'on'}
request = rf.post('/communications/subscribe/', post_data)
request._dont_enforce_csrf_checks = True

SessionMiddleware().process_request(request)
request.session.save()

messages = FallbackStorage(request)
setattr(request, '_messages', messages)

response = subscribe(request)
print('response type:', type(response))
print('response status:', getattr(response, 'status_code', None))
print('response url:', getattr(response, 'url', None))
print('session pending:', request.session.get('pending_subscription'))
