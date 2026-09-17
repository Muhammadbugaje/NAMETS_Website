from core.dashboard_widgets import DashboardWidget, register_widget
from .models import Announcement, Subscriber

class AnnouncementsWidget(DashboardWidget):
    permission = "communications.view_announcement"
    label = "Announcements"
    icon = "fa-bullhorn"
    url_name = "admin:communications_announcement_changelist"

    def get_count(self):
        return Announcement.objects.count()

class SubscribersWidget(DashboardWidget):
    permission = "communications.view_subscriber"
    label = "Subscribers"
    icon = "fa-envelope"
    url_name = "admin:communications_subscriber_changelist"

    def get_count(self):
        return Subscriber.objects.filter(is_active=True).count()

register_widget(AnnouncementsWidget())
register_widget(SubscribersWidget())