from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'superapp.apps.whatsapp'
    verbose_name = 'WhatsApp Integration'
