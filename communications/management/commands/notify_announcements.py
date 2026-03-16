from django.core.management.base import BaseCommand
from django.utils import timezone  # type: ignore
from communications.models import Subscriber, Announcement
from communications.notification_utils import send_notification_email

class Command(BaseCommand):
    help = 'Send email notifications for new announcements'

    def handle(self, *args, **options):
        # Find announcements published in the last 24 hours (or since last run)
        # For simplicity, we'll send for all active announcements that haven't been notified
        # This is a basic version; you'd need a way to track sent notifications.
        announcements = Announcement.objects.filter(
            is_active=True,
            publish_at__lte=timezone.now(),
            expire_at__gte=timezone.now()  # not expired
        )[:5]  # limit for demo

        if not announcements:
            return

        subscribers = Subscriber.objects.filter(is_active=True, notify_announcements=True)
        for sub in subscribers:
            context = {
                'subscriber': sub,
                'announcements': announcements,
                'unsubscribe_url': sub.get_unsubscribe_url(),
            }
            send_notification_email(
                subject='New Announcements from NAMETS',
                template_name='emails/new_announcements.html',
                context=context,
                recipient_list=[sub.email],
            )
        self.stdout.write(self.style.SUCCESS(f'Sent announcements to {subscribers.count()} subscribers'))