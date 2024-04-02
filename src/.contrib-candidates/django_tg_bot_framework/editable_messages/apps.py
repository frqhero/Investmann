from django.apps import AppConfig


class EditableMessagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_tg_bot_framework.editable_messages'
    verbose_name = 'Редактируемые сообщения'
