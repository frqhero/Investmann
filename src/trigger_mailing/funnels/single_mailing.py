from datetime import timedelta
from time import time
import traceback
from typing import Any

import rollbar
from pydantic import Field
from yostate import Router, BaseState, Locator

from django.conf import settings
from django.db import models
from django.utils.timezone import now

from django_tg_bot_framework.funnels import AbstractFunnelEvent
from django_workers import AbstractTaskQueue, TaskError

from ..models import Lead

FIRST_MAILING_FUNNEL_SLUG = 'first_mailing'
SECOND_MAILING_FUNNEL_SLUG = 'second_mailing'


class LeadNavigatedToMainMenu(AbstractFunnelEvent):
    funnel_slug: str = FIRST_MAILING_FUNNEL_SLUG


class LeadLaunchedSecondMailing(AbstractFunnelEvent):
    funnel_slug: str = SECOND_MAILING_FUNNEL_SLUG


class MailingWasSentToLead(AbstractFunnelEvent):
    pass


class MailingTargetActionAcceptedByLead(AbstractFunnelEvent):
    action: str = Field(
        default='',
        description='Action choices was selected by lead.',
    )


class LeadUnsubscribed(AbstractFunnelEvent):
    pass


router = Router()


@router.register('/')
class StartState(BaseState):
    def process(self, event: Any) -> Locator | None:
        match event:
            case LeadNavigatedToMainMenu() | LeadLaunchedSecondMailing():
                return Locator('/mailing-queue/')


@router.register('/mailing-queue/')
class MailingQueueState(BaseState):
    """Lead was placed to queue and waits for mailing."""

    added_to_queue_at: float = Field(
        default_factory=time,
        description='Timestamp value lead was added to mailing queue.',
    )
    waiting_till: float = Field(
        default_factory=lambda: time() + timedelta(minutes=1).total_seconds(),
        description='Timestamp value determine a moment mailing should be send after.',
    )
    expired_after: float = Field(
        default_factory=lambda: time() + timedelta(hours=24).total_seconds(),
        description='Timestamp value determine a moment mailing is considered expired after.',
    )

    def process(self, event: Any) -> Locator | None:
        match event:
            case MailingWasSentToLead():
                return Locator('/message-sent/')


@router.register('/message-sent/')
class MessageSentState(BaseState):
    message_sent_at: float = Field(default_factory=time)

    def process(self, event: Any) -> Locator | None:
        match event:
            case MailingTargetActionAcceptedByLead():
                return Locator('/button-pressed/', params={
                    'action_selected': event.action,
                })
            case LeadUnsubscribed():
                return Locator('/unsubscribed/')


@router.register('/button-pressed/')
class ButtonPressed(BaseState):
    accepted_at: float = Field(default_factory=time)
    action_selected: str = ''


@router.register('/unsubscribed/')
class Unsubscribed(BaseState):
    unsubscribed_at: float = Field(default_factory=time)
    action_selected: str = ''


class MailingQueue(AbstractTaskQueue):
    def get_pending_tasks_queryset(self) -> models.QuerySet:
        return (
            Lead.objects
            .annotate_with_tg_chat_id()
            .exclude(tg_chat_id=None)
            .ready_for_mailing()
            .order_by('state_machine_locator__params__added_to_queue_at')
        )

    def exclude_cycled_failed_tasks(
        self,
        queryset: models.QuerySet,
    ) -> models.QuerySet:
        return queryset.exclude_mailing_failed()

    def handle_task(self, queryset_item: models.Model):
        from tg_bot.states import state_machine as primary_state_machine
        with primary_state_machine.restore_session(tg_chat_id=queryset_item.tg_chat_id) as session:
            match queryset_item.funnel_slug:
                case slug if slug == FIRST_MAILING_FUNNEL_SLUG:
                    session.switch_to(Locator('/first-trigger-mailing/'))
                case slug if slug == SECOND_MAILING_FUNNEL_SLUG:
                    session.switch_to(Locator('/second-trigger-mailing/'))

    def process_task_error(self, queryset_item: models.Model, error: TaskError) -> None:
        queryset_item.mailing_failed_at = now()
        queryset_item.mailing_failure_reason_code = error.reason_code
        queryset_item.mailing_failure_description = error.description
        queryset_item.mailing_failure_debug_details = ''.join(traceback.format_exception(error))
        queryset_item.save(update_fields=[
            'mailing_failed_at',
            'mailing_failure_reason_code',
            'mailing_failure_description',
            'mailing_failure_debug_details',
        ])
        if not hasattr(settings, "ROLLBAR"):
            return
        rollbar.init(
            access_token=settings.ROLLBAR["access_token"],
            environment=settings.ROLLBAR["environment"],
            root=settings.ROLLBAR["root"],
            locals=settings.ROLLBAR["locals"],
        )
        rollbar.report_exc_info()


# Task queue will be used by run_worker management command
# Import path changes should be reflated in management command arguments
mailing_queue = MailingQueue()
