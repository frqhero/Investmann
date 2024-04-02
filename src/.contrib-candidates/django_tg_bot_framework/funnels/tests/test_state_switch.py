from typing import Any

from pydantic import Field
import pytest
from yostate import Router, BaseState, Locator

from django_tg_bot_framework.funnels import AbstractFunnelEvent

# FIXME should replace with separate model independent from Starter Pack code
from trigger_mailing.models import Lead

from ..state_machine import FunnelStateMachine

FUNNEL_SLUG = 'first_mailing'


class BaseFunnelEvent(AbstractFunnelEvent):
    funnel_slug: str = FUNNEL_SLUG


class LeadNavigatedToMainMenu(BaseFunnelEvent):
    pass


class MailingWasSentToLead(BaseFunnelEvent):
    pass


class TargetActionAcceptedByLead(BaseFunnelEvent):
    action: str = Field(default='', description='Action choices was selected by lead.')


router = Router()


@router.register('/')
class StartState(BaseState):
    def process(self, event: Any) -> Locator | None:
        match event:
            case LeadNavigatedToMainMenu():
                return Locator('/mailing-queue/')


@router.register('/mailing-queue/')
class MailingQueueState(BaseState):
    """Lead was placed to queue and waits for mailing."""

    def process(self, event: Any) -> Locator | None:
        match event:
            case MailingWasSentToLead():
                return Locator('/message-sent/')


@router.register('/message-sent/')
class MessageSentState(BaseState):
    def process(self, event: Any) -> Locator | None:
        match event:
            case TargetActionAcceptedByLead():
                return Locator('/button-pressed/', params={
                    'action_selected': event.action,
                })


@router.register('/button-pressed/')
class ButtonPressed(BaseState):
    action_selected: str = ''


funnel_state_machine = FunnelStateMachine(
    router_mapping={FUNNEL_SLUG: router},
    lead_model=Lead,
)


@pytest.mark.django_db
def test_empty_transitions_list_processing():
    """Прикладной программист -- Обработать события воронок: !func

    Пустой список событий: !story
    """  # noqa D400
    funnel_state_machine.switch_to_many([])


@pytest.mark.django_db
def test_lead_creation():
    tg_user_id = 11

    funnel_state_machine.switch_to_many([
        ((tg_user_id, FUNNEL_SLUG), Locator('/mailing-queue/')),
    ])

    assert Lead.objects.count() == 1
    created_lead = Lead.objects.first()
    assert created_lead.tg_user_id == tg_user_id
    assert created_lead.funnel_slug == FUNNEL_SLUG
    assert created_lead.state_machine_locator.state_class_locator == '/mailing-queue/'


# TODO Добавить больше автотестов
