from core.dashboard_widgets import DashboardWidget, register_widget
from .models import Item

class LostFoundWidget(DashboardWidget):
    permission = "lostfound.view_item"
    label = "Lost & Found Items"
    icon = "fa-search"
    url_name = "admin:lostfound_item_changelist"

    def get_count(self):
        return Item.objects.filter(is_active=True).count()

register_widget(LostFoundWidget())