from core.dashboard_widgets import DashboardWidget, register_widget
from .models import BorrowRecord
from django.utils import timezone

class OverdueItemsWidget(DashboardWidget):
    permission = "business.view_borrowrecord"
    label = "Overdue Items"
    icon = "fa-box-open"
    url_name = "admin:business_borrowrecord_changelist"

    def get_count(self):
        return BorrowRecord.objects.filter(
            status='borrowed',
            expected_return_date__lt=timezone.now()
        ).count()

register_widget(OverdueItemsWidget())