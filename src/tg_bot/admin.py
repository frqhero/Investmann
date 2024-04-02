from django.conf import settings
from django.contrib import admin

from django_tg_bot_framework.editable_messages.admin import EditableMessagesAdmin, admin_register

from .models import Conversation
from .states import message_router


@admin_register
class BotMessagesAdmin(EditableMessagesAdmin):
    message_router = message_router
    languages = settings.BOT_LANGUAGES


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = [
        'tg_chat_id',
        'tg_user_id',
        'get_current_language',
        'created_at',
        'interacted_at',
    ]
    date_hierarchy = 'created_at'
    search_fields = [
        'tg_chat_id',
        'tg_user_id',
        'last_update_tg_username',
    ]

    fieldsets = [
        (
            None,
            {
                "fields": [
                    "tg_chat_id",
                    "tg_user_id",
                    "last_update_language_code",
                    "force_language",
                    "last_update_tg_username",
                ],
            },
        ),
        (
            "Стейт-машина",
            {
                "fields": [
                    "state_machine_locator",
                ],
            },
        ),
        (
            "Дополнительно",
            {
                "classes": ["collapse"],
                "fields": [
                    "created_at",
                    "interacted_at",
                ],
            },
        ),
    ]

    class Media:
        css = {
            'all': [
                'admin/sticky-save.css',
            ],
        }
        js = [
            'admin/save-hotkey.js',
        ]

    @admin.display(description='Язык пользователя')
    def get_current_language(self, obj: Conversation):
        return obj.force_language or obj.last_update_language_code or 'unknown'
