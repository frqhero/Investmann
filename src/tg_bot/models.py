from django.db import models

from django_tg_bot_framework.private_chats import (
    AbstractPrivateChatSessionModel,
)


class Conversation(AbstractPrivateChatSessionModel):
    force_language = models.CharField(
        'Выбранный пользователем язык',
        max_length=8,
        blank=True,
        db_index=True,
        help_text=(
            'Языковой код, выбранный пользователем вручную'
        ),
    )
