from functools import partial
from time import time
from datetime import timedelta
from typing import Any

from django.db import connection
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
def test_funnel_start_to_end_traversing():
    tg_user_id = 1

    events_queue = [
        LeadNavigatedToMainMenu(tg_user_id=tg_user_id),
        MailingWasSentToLead(tg_user_id=tg_user_id),
        TargetActionAcceptedByLead(tg_user_id=tg_user_id),
    ]

    funnel_state_machine.process_many(events_queue)

    lead = Lead.objects.get(tg_user_id=tg_user_id, funnel_slug=FUNNEL_SLUG)
    assert lead.state_machine_locator
    assert lead.state_machine_locator.state_class_locator == '/button-pressed/'


@pytest.mark.django_db
def test_state_machine_saving():
    tg_user_id = 1
    get_lead = partial(Lead.objects.get, tg_user_id=tg_user_id, funnel_slug=FUNNEL_SLUG)

    funnel_state_machine.process_many([LeadNavigatedToMainMenu(tg_user_id=tg_user_id)])
    assert get_lead().state_machine_locator.state_class_locator == '/mailing-queue/'

    funnel_state_machine.process_many([MailingWasSentToLead(tg_user_id=tg_user_id)])
    assert get_lead().state_machine_locator.state_class_locator == '/message-sent/'

    funnel_state_machine.process_many([
        TargetActionAcceptedByLead(tg_user_id=tg_user_id),
    ])
    assert get_lead().state_machine_locator.state_class_locator == '/button-pressed/'


@pytest.mark.django_db
def test_reaction_on_obsolete_state_machine_locator():
    """Прикладной программист -- Обработать события воронок: !func

    Устаревший локатор у лида из БД: !story
    """  # noqa D400
    obsolete_lead = Lead.objects.create(
        tg_user_id=1,
        funnel_slug=FUNNEL_SLUG,
        state_machine_locator=Locator(
            state_class_locator='/not/exist/',
        ),
    )
    funnel_state_machine.process_many([
        LeadNavigatedToMainMenu(tg_user_id=obsolete_lead.tg_user_id),
    ])

    updated_leads = Lead.objects.all()
    updated_state_class_locators = [lead.state_machine_locator.state_class_locator for lead in updated_leads]
    assert updated_state_class_locators == ['/mailing-queue/']


@pytest.mark.django_db
def test_reaction_on_broken_state_machine_locator():
    """Прикладной программист -- Обработать события воронок: !func

    Сломан локатор в БД: !story
    """  # noqa D400
    cursor = connection.cursor()
    query = ("INSERT INTO trigger_mailing_lead "
             "(tg_user_id, funnel_slug, state_machine_locator, "
             "mailing_failure_reason_code, mailing_failure_description, mailing_failure_debug_details) "
             "VALUES (2, 'first_mailing', '{\"garbage\": true}', '', '', '')")
    cursor.execute(query)

    funnel_state_machine.process_many([
        LeadNavigatedToMainMenu(tg_user_id=2),
    ])

    updated_leads = Lead.objects.all()
    updated_state_class_locators = [lead.state_machine_locator.state_class_locator for lead in updated_leads]
    assert updated_state_class_locators == ['/mailing-queue/']


@pytest.mark.django_db
def test_events_collecting_with_direct_access():
    tg_user_id = 1

    with funnel_state_machine.process_collected() as events_queue:
        events_queue.append(LeadNavigatedToMainMenu(tg_user_id=tg_user_id))

        events_queue.extend([
            MailingWasSentToLead(tg_user_id=tg_user_id),
            TargetActionAcceptedByLead(tg_user_id=tg_user_id),
        ])

    lead = Lead.objects.get(tg_user_id=tg_user_id, funnel_slug=FUNNEL_SLUG)
    assert lead.state_machine_locator
    assert lead.state_machine_locator.state_class_locator == '/button-pressed/'


@pytest.mark.django_db
def test_events_collecting_with_contextvar():
    tg_user_id = 1

    with funnel_state_machine.process_collected():
        funnel_state_machine.push_event(LeadNavigatedToMainMenu(tg_user_id=tg_user_id))
        funnel_state_machine.push_events([
            MailingWasSentToLead(tg_user_id=tg_user_id),
            TargetActionAcceptedByLead(
                tg_user_id=tg_user_id,
                action='buy_anything',
            ),
        ])

    lead = Lead.objects.get(tg_user_id=tg_user_id, funnel_slug=FUNNEL_SLUG)
    assert lead.state_machine_locator
    assert lead.state_machine_locator.state_class_locator == '/button-pressed/'
    assert lead.state_machine_locator.params.get('action_selected') == 'buy_anything'


@pytest.mark.django_db
def test_dynamic_routing():
    """Прикладной программист -- Обработать события воронок: !func

    События динамически создаваемых воронок: !story
    """  # noqa D400
    tg_user_id = 1
    sm_with_lot_of_funnels = FunnelStateMachine(
        router_mapping=lambda funnel_slug: router,
        lead_model=Lead,
    )

    with sm_with_lot_of_funnels.process_collected() as events_queue:
        events_queue.extend([
            BaseFunnelEvent(tg_user_id=tg_user_id, funnel_slug='first_funnel'),
            BaseFunnelEvent(tg_user_id=tg_user_id, funnel_slug='second_funnel'),
            BaseFunnelEvent(tg_user_id=tg_user_id, funnel_slug='third_funnel'),
        ])

    leads = Lead.objects.filter(tg_user_id=tg_user_id).values_list('funnel_slug', flat=True)
    assert set(leads) == {
        'first_funnel',
        'second_funnel',
        'third_funnel',
    }


@pytest.mark.django_db
def test_empty_event_list_processing():
    """Прикладной программист -- Обработать события воронок: !func

    Пустой список событий: !story
    """  # noqa D400
    funnel_state_machine.process_many([])


# TODO Добавить больше автотестов:
# Прикладной программист -- Обработать события воронок: !func
#   Внешние события по отношению к Tg: !story
#   Несколько параллельно запущенных стейт-машин: !story

#   Событие для нового лида: !story
#   Несколько событий разом: !story

#   Микс событий из разных воронок: !story
#   Смешаны события для разных лидов: !story

#   Одно событие без контекста: !story
#   Одно событие без контекста, не AbstractFunnelEvent: !story  # отказ
#   Одно событие внутри контекста: !story
#   Одно событие снаружи контекста: !story  # отказ, вижу сообщение о необходимости настроить контекст
#   Одно событие, не AbstractFunnelEvent: !story  # отказ, вижу сообщение о необходимости настроить контекст

#   Много событий без контекста: !story
#   Много событий без контекста, среди которых есть не AbstractFunnelEvent: !story  # отказ
#   Много событий внутри контекста: !story
#   Много событий снаружи контекста: !story  # отказ, вижу сообщение о необходимости настроить контекст
#   Много событий, среди которых есть не AbstractFunnelEvent: !story  # отказ, вижу сообщение о необходимости
#   настроить контекст


@pytest.mark.django_db
def test_outer_push():
    tg_user_id = 1

    with pytest.raises(FunnelStateMachine.OuterPushError):
        funnel_state_machine.push_event(LeadNavigatedToMainMenu(tg_user_id=tg_user_id))

    with pytest.raises(FunnelStateMachine.OuterPushError):
        funnel_state_machine.push_events([LeadNavigatedToMainMenu(tg_user_id=tg_user_id)])


@pytest.mark.django_db
def test_unknown_funnels_ignoring():
    tg_user_id = 1
    sm_with_lot_of_funnels = FunnelStateMachine(
        router_mapping={'known_funnel': router},
        lead_model=Lead,
    )

    with sm_with_lot_of_funnels.process_collected() as events_queue:
        events_queue.extend([
            BaseFunnelEvent(tg_user_id=tg_user_id, funnel_slug='known_funnel'),
            BaseFunnelEvent(tg_user_id=tg_user_id, funnel_slug='unknown_funnel'),
        ])

    leads = Lead.objects.filter(tg_user_id=tg_user_id).values_list('funnel_slug', flat=True)
    assert set(leads) == {'known_funnel'}


@pytest.mark.django_db
def test_bulk_append_to_mailing_list(n=1000):
    """Прикладной программист -- Наполнить список рассылки: !func

    Тысяча лидов: !story
    """  # noqa D400

    class LeadWasAppendedToMailingList(AbstractFunnelEvent):
        funnel_slug: str = FUNNEL_SLUG

    mailing_router = Router()

    @mailing_router.register('/')
    class StartState(BaseState):
        def process(self, event: Any) -> Locator | None:
            match event:
                case LeadWasAppendedToMailingList():
                    return Locator('/mailing-queue/')

    @mailing_router.register('/mailing-queue/')
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

    funnel_state_machine = FunnelStateMachine(
        router_mapping={FUNNEL_SLUG: mailing_router},
        lead_model=Lead,
    )

    events = [
        LeadWasAppendedToMailingList(tg_user_id=1000 + counter) for counter in range(1, n)
    ]
    funnel_state_machine.process_many(events)

    waiting_leads = Lead.objects.filter(state_machine_locator__state_class_locator='/mailing-queue/')
    assert waiting_leads.count() == n - 1
