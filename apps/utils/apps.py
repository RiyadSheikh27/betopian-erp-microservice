from django.apps import AppConfig

class UtilsConfig(AppConfig):
    name = "apps.utils"

    def ready(self):
        from django.core.signals import request_started

        from .media_cleanup import connect_media_cleanup_signals
        from .views import apply_media_settings

        connect_media_cleanup_signals()
        request_started.connect(apply_media_settings)