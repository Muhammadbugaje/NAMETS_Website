from core.dashboard_widgets import DashboardWidget, register_widget
from .models import Event
from django.utils import timezone

class UpcomingEventsWidget(DashboardWidget):
    permission = "events.view_event"
    label = "Upcoming Events"
    icon = "fa-calendar-alt"
    url_name = "events:list"

    def get_count(self):
        return Event.objects.filter(is_active=True, start_datetime__gte=timezone.now()).count()

register_widget(UpcomingEventsWidget())