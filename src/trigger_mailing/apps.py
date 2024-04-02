from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trigger_mailing'
    verbose_name = 'Триггерная воронка'
