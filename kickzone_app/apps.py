from django.apps import AppConfig


class KickzoneAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kickzone_app'
    
    def ready(self):
        import kickzone_app.signals
