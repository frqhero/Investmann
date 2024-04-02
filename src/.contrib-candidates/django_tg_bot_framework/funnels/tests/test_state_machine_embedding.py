import pytest
from typing import Any

from yostate import Locator, Router, BaseState

from ...private_chats import PrivateChatStateMachine, PrivateChatState

from ..events import AbstractFunnelEvent
from ..state_machine import FunnelStateMachine

# FIXME should replace with separate model independent from Starter Pack code
from tg_bot.models import Conversation as SessionModel

# FIXME should replace with separate model independent from Starter Pack code
from trigger_mailing.models import Lead


FUNNEL_SLUG = 'first_mailing'


class LeadNavigatedToMainMenu(AbstractFunnelEvent):
    funnel_slug: str = FUNNEL_SLUG


router = Router()


@router.register('/')
class StartState(BaseState):
    def process(self, event: Any) -> Locator | None:
        match event:
            case LeadNavigatedToMainMenu():
                return Locator('/mailing-queue/')


@router.register('/mailing-queue/')
class MailingQueueState(BaseState):
    pass


funnel_state_machine = FunnelStateMachine(
    router_mapping={FUNNEL_SLUG: router},
    lead_model=Lead,
)


@pytest.mark.django_db
def test_integrations_with_private_chat_state_machine():
    """Прикладной программист -- Встроить стейт-машину воронок в диалоговую стейт-машину: !func

    Встроить в приватные чаты: !story
        успех:
            - Вижу движение лида по воронке в соответствии с событиями в диалоге
            - Вижу в коде только запуск диалоговой стейт-машины
    """  # noqa D400
    tg_chat_id, tg_user_id = 90001, 4114

    SessionModel.objects.create(
        tg_chat_id=tg_chat_id,
        tg_user_id=tg_user_id,
    )

    router = Router()
    dialog_state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
        context_funcs=[
            funnel_state_machine.process_collected,
            lambda: AbstractFunnelEvent.set_default_tg_user_id(SessionModel.current.tg_user_id),
        ],
    )

    @router.register('/main-menu/')
    class MainMenuState(PrivateChatState):
        def enter_state(self) -> Locator | None:
            funnel_state_machine.push_event(LeadNavigatedToMainMenu())

    with dialog_state_machine.restore_session(tg_chat_id=tg_chat_id) as session:
        session.switch_to(Locator('/main-menu/'))

    lead_locator = Lead.objects.get(tg_user_id=tg_user_id).state_machine_locator
    assert lead_locator
    assert lead_locator.state_class_locator == '/mailing-queue/'
