from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communications'

    def ready(self):
        import communications.signals  # noqa: F401 — registers the @receiver
        import communications.dashboard_widgets