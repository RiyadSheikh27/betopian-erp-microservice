from django.apps import AppConfig

class UtilsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.utils"

    def ready(self):
        from .views import load_media_handling
        load_media_handling()