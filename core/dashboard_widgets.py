# core/dashboard_widgets.py

class DashboardWidget:
    permission = ""          # e.g., "communications.view_announcement"
    label = ""               # e.g., "Announcements"
    icon = ""                # Font Awesome class, e.g., "fa-bullhorn"
    url_name = ""            # URL name for the link (use reverse)

    def get_count(self):
        """Return the count to display on the widget."""
        raise NotImplementedError

# Registry
WIDGET_REGISTRY = []

def register_widget(widget_instance):
    WIDGET_REGISTRY.append(widget_instance)

def widgets_for_permissions(user_permission_codenames):
    """
    Returns list of widgets (with count) that the user has permission for.
    """
    matched = []
    for widget in WIDGET_REGISTRY:
        if widget.permission in user_permission_codenames:
            matched.append({
                'widget': widget,
                'count': widget.get_count(),
            })
    return matched