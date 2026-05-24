from django.apps import AppConfig

class UtilsConfig(AppConfig):
    name = "apps.utils"

    def ready(self):
        from django.core.signals import request_started
        from .views import apply_media_settings
        request_started.connect(apply_media_settings)