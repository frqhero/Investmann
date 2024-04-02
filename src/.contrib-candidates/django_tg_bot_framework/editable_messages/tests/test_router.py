from django_tg_bot_framework.private_chats import PrivateChatState
from mysent import MessageLocator, Message
from yostate import Router
from ..renderers import MockTgRenderer
from ..tg_message_router import EditableMessagesRouter


def test_registration_of_state_messages():
    router = Router()
    message_router = EditableMessagesRouter(MockTgRenderer(lambda: 1, lambda: 'ru'))

    welcome_contract = Message(sense='Добро пожаловать')
    main_contract = Message(sense='Главное меню')

    @router.register('/welcome/')
    class FirstUserMessageState(PrivateChatState):
        class EditableMessages:
            welcome = welcome_contract

    @router.register('/main/')
    class SecondUserMessageState(PrivateChatState):
        _editable_messages = {
            'main': main_contract,
        }

    message_router.fill_message_router_from_states(router)

    assert list(message_router.keys()) == [
        MessageLocator(namespace='/welcome/', name='welcome'),
        MessageLocator(namespace='/main/', name='main'),
    ]
    assert list(message_router.values()) == [welcome_contract, main_contract]
