from core.dashboard_widgets import DashboardWidget, register_widget
from .models import Gallery

class GalleryWidget(DashboardWidget):
    permission = "gallery.view_gallery"
    label = "Gallery Albums"
    icon = "fa-images"
    url_name = "admin:gallery_gallery_changelist"

    def get_count(self):
        return Gallery.objects.count()

register_widget(GalleryWidget())