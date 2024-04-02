from time import time

from django.db import models

from django_tg_bot_framework.funnels import AbstractFunnelLeadModel


class LeadQuerySet(models.QuerySet):
    def mailing_failed(self):
        return self.exclude(mailing_failed_at=None)

    def exclude_mailing_failed(self):
        return self.filter(mailing_failed_at=None)

    def ready_for_mailing(self, timestamp: float | None = None):
        timestamp = time() if timestamp is None else timestamp
        return (
            self
            .exclude_mailing_failed()
            .filter(
                state_machine_locator__state_class_locator='/mailing-queue/',
                state_machine_locator__params__waiting_till__lte=timestamp,
                state_machine_locator__params__expired_after__gte=timestamp,
            )
        )

    def postponed_mailing(self, timestamp: float | None = None):
        timestamp = time() if timestamp is None else timestamp
        return (
            self
            .exclude_mailing_failed()
            .filter(
                state_machine_locator__state_class_locator='/mailing-queue/',
                state_machine_locator__params__waiting_till__gt=timestamp,
                state_machine_locator__params__expired_after__gt=timestamp,
            )
        )

    def annotate_with_tg_username(self):
        from tg_bot.models import Conversation
        related_conversations = Conversation.objects.filter(
            tg_user_id=models.OuterRef('tg_user_id'),
        )

        return self.annotate(
            tg_username=models.Subquery(related_conversations.values('last_update_tg_username')[:1]),
        )

    def annotate_with_tg_chat_id(self):
        from tg_bot.models import Conversation
        related_conversations = Conversation.objects.filter(
            tg_user_id=models.OuterRef('tg_user_id'),
        )

        return self.annotate(
            tg_chat_id=models.Subquery(related_conversations.values('tg_chat_id')[:1]),
        )


class Lead(AbstractFunnelLeadModel):
    mailing_failed_at = models.DateTimeField(
        'когда случилась ошибка',
        db_index=True,
        null=True,
        blank=True,
        help_text='Если поле осталось пустым после рассылки — значит рассылка прошла успешно.',
    )
    mailing_failure_reason_code = models.CharField(
        'код ошибки рассылки',
        db_index=True,
        blank=True,
        max_length=100,
        help_text='Англоязычный код ошибки по результатам рассылки, например "endless_loop".',
    )
    mailing_failure_description = models.TextField(
        'описание ошибки рассылки',
        blank=True,
        help_text='Описание для пользователя.',
    )

    mailing_failure_debug_details = models.TextField(
        'отладочная информация об ошибке рассылки',
        blank=True,
        help_text='Описание ошибки рассылки. Поле хранит отладочную информацию для программиста.',
    )

    objects = LeadQuerySet.as_manager()
