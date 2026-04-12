from django.apps import AppConfig

class NametsNotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "namets_notifications"
    verbose_name = "NAMETS Notifications"

    def ready(self):
        from .signals import connect_signals
        connect_signals()