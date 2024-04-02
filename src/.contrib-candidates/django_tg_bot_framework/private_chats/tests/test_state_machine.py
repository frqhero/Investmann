from unittest.mock import MagicMock

import pytest
from tg_api import Update
from yostate import Router, Locator
from django.test import override_settings

# FIXME should replace with separate model independent from Starter Pack code
from tg_bot.models import Conversation as SessionModel

from .. import (
    PrivateChatStateMachine,
    PrivateChatState,
    PrivateChatMessageReceived,
    PrivateChatMessageEdited,
    PrivateChatCallbackQuery,
)

DEFAULT_TG_CHAT_ID, DEFAULT_TG_USER_ID, DEFAULT_TG_USERNAME, DEFAULT_TG_LANGUAGE = 90001, 4114, 'ivan_petrov', 'ru_ru'
DEFAULT_TG_UPDATE_PAYLOAD = {
    'update_id': 1,
    'message': {
        'message_id': 101,
        'from': {
            'id': DEFAULT_TG_USER_ID,
            'is_bot': False,
            'first_name': 'Иван Петров',
            'username': DEFAULT_TG_USERNAME,
            'language_code': DEFAULT_TG_LANGUAGE,
        },
        'date': 0,
        'chat': {
            'id': DEFAULT_TG_CHAT_ID,
            'type': 'private',
        },
    },
}
DEFAULT_TG_UPDATE = Update.parse_obj(DEFAULT_TG_UPDATE_PAYLOAD)


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_get_old_session():
    assert not SessionModel.objects.all().count()

    SessionModel.objects.create(
        tg_chat_id=DEFAULT_TG_CHAT_ID,
        tg_user_id=DEFAULT_TG_USER_ID,
    )

    router = Router()

    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    with state_machine.restore_session(tg_chat_id=DEFAULT_TG_CHAT_ID):
        pass


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_raise_old_session_not_found():
    assert not SessionModel.objects.all().count()

    router = Router()

    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    with pytest.raises(state_machine.NotFoundSessionError):
        with state_machine.restore_session(tg_chat_id=DEFAULT_TG_CHAT_ID):
            pass


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_create_new_session_from_tg_update():
    assert not SessionModel.objects.all().count()

    router = Router()

    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    with state_machine.restore_or_create_session_from_tg_update(DEFAULT_TG_UPDATE):
        pass

    session_db_dump = SessionModel.objects.get(
        tg_chat_id=DEFAULT_TG_CHAT_ID,
        tg_user_id=DEFAULT_TG_USER_ID,
    )
    assert session_db_dump.last_update_tg_username == ''
    assert session_db_dump.last_update_language_code == ''
    assert session_db_dump.interacted_at is None
    assert session_db_dump.state_machine_locator is None


@pytest.mark.parametrize(
    ['explanation_snippet', 'wrong_update_payload'],
    [
        [
            'update of unknown type',
            {
                'update_id': 1,
            },
        ],
        [
            'without author specified',
            {
                'update_id': 1,
                'message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {'from': None},
            },
        ],
        [
            'non private chat',
            {
                'update_id': 1,
                'message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {
                    'chat': DEFAULT_TG_UPDATE_PAYLOAD['message']['chat'] | {'type': 'channel'},
                },
            },
        ],
        [
            'without author specified',
            {
                'update_id': 1,
                'edited_message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {'from': None},
            },
        ],
        [
            'non private chat',
            {
                'update_id': 1,
                'edited_message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {
                    'chat': DEFAULT_TG_UPDATE_PAYLOAD['message']['chat'] | {'type': 'channel'},
                },
            },
        ],
        [
            'without message specified',
            {
                'update_id': 1,
                'callback_query': {
                    'id': 1,
                    'data': '-',
                    'from': DEFAULT_TG_UPDATE_PAYLOAD['message']['from'],
                },
            },
        ],
        [
            'non private chat',
            {
                'update_id': 1,
                'callback_query': {
                    'id': 1,
                    'data': '-',
                    'from': DEFAULT_TG_UPDATE_PAYLOAD['message']['from'],
                    'message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {
                        'chat': DEFAULT_TG_UPDATE_PAYLOAD['message']['chat'] | {'type': 'channel'},
                    },
                },
            },
        ],
    ],
)
@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_raise_on_session_creation_with_wrong_tg_update_object(explanation_snippet, wrong_update_payload):
    assert not SessionModel.objects.all().count()

    wrong_update = Update.parse_obj(wrong_update_payload)
    router = Router()

    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    with pytest.raises(state_machine.IrrelevantTgUpdate, match=explanation_snippet):
        with state_machine.restore_or_create_session_from_tg_update(wrong_update):
            pass


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_save_last_update_info():
    assert not SessionModel.objects.all().count()

    router = Router()

    @router.register('/')
    class RootState(PrivateChatState):
        ...

    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    with state_machine.restore_or_create_session_from_tg_update(DEFAULT_TG_UPDATE) as session:
        assert not session.crawler.attached
        session.switch_to(Locator('/'))
        session.process_tg_update(DEFAULT_TG_UPDATE)

    session_db_dump = SessionModel.objects.get(
        tg_chat_id=DEFAULT_TG_CHAT_ID,
        tg_user_id=DEFAULT_TG_USER_ID,
    )
    assert session_db_dump.last_update_tg_username == DEFAULT_TG_USERNAME
    assert session_db_dump.last_update_language_code == DEFAULT_TG_LANGUAGE
    assert session_db_dump.interacted_at is not None
    assert session_db_dump.state_machine_locator == Locator('/')


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_save_and_restore_state():
    assert not SessionModel.objects.all().count()

    router = Router()

    @router.register('/')
    class RootState(PrivateChatState):
        ...

    @router.register('/another/')
    class AnotherState(PrivateChatState):
        ...

    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    with state_machine.restore_or_create_session_from_tg_update(DEFAULT_TG_UPDATE) as session:
        assert not session.crawler.attached
        session.switch_to(Locator('/another/'))

    session_db_dump = SessionModel.objects.get(tg_chat_id=DEFAULT_TG_CHAT_ID, tg_user_id=DEFAULT_TG_USER_ID)
    assert session_db_dump.state_machine_locator == Locator('/another/')

    with state_machine.restore_or_create_session_from_tg_update(DEFAULT_TG_UPDATE) as session:
        assert session.crawler.current_state.locator == Locator('/another/')


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_reset_obsolete_locator_on_session_restore():
    assert not SessionModel.objects.all().count()

    old_router = Router()
    new_router = Router()

    @old_router.register('/')
    @new_router.register('/')
    class RootState(PrivateChatState):
        ...

    @old_router.register('/another/')
    class AnotherState(PrivateChatState):
        ...

    first_state_machine = PrivateChatStateMachine(
        router=old_router,
        session_model=SessionModel,
    )

    with first_state_machine.restore_or_create_session_from_tg_update(DEFAULT_TG_UPDATE) as session:
        assert not session.crawler.attached
        session.switch_to(Locator('/another/'))

    session_db_dump = SessionModel.objects.get(tg_chat_id=DEFAULT_TG_CHAT_ID)
    assert session_db_dump.state_machine_locator == Locator('/another/')

    second_state_machine = PrivateChatStateMachine(
        router=new_router,
        session_model=SessionModel,
    )

    with second_state_machine.restore_or_create_session_from_tg_update(DEFAULT_TG_UPDATE) as session:
        assert not session.crawler.attached

    session_db_dump = SessionModel.objects.get(tg_chat_id=DEFAULT_TG_CHAT_ID, tg_user_id=DEFAULT_TG_USER_ID)
    assert session_db_dump.state_machine_locator is None


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_switch_state_on_tg_update():
    SessionModel.objects.create(
        tg_chat_id=DEFAULT_TG_CHAT_ID,
        tg_user_id=DEFAULT_TG_USER_ID,
        state_machine_locator=Locator(
            state_class_locator='/first/',
            params={'counter': 7},
        ),
    )

    router = Router()

    @router.register('/')
    class RootState(PrivateChatState):
        ...

    @router.register('/first/')
    class FirstState(PrivateChatState):
        counter: int

        def process_message_received(self, event: PrivateChatMessageReceived):
            assert isinstance(event, PrivateChatMessageReceived)
            return Locator('/first/', params={'counter': self.counter + 1})

    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    with state_machine.restore_session(tg_chat_id=DEFAULT_TG_CHAT_ID) as session:
        assert session.crawler.attached
        assert session.crawler.current_state.locator == Locator('/first/', params={
            'counter': 7,
        })
        session.process_tg_update(DEFAULT_TG_UPDATE)

    session_db_dump = SessionModel.objects.get(tg_chat_id=DEFAULT_TG_CHAT_ID)
    assert session_db_dump.state_machine_locator == Locator('/first/', params={'counter': 8})


@pytest.mark.parametrize(
    'wrong_update_payload',
    [
        # Update of unknown type
        {
            'update_id': 1,
        },
        # Without author specified
        {
            'update_id': 1,
            'message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {'from': None},
        },
        # Non private chat
        {
            'update_id': 1,
            'message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {
                'chat': DEFAULT_TG_UPDATE_PAYLOAD['message']['chat'] | {'type': 'channel'},
            },
        },
        # Without author specified
        {
            'update_id': 1,
            'edited_message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {'from': None},
        },
        # Non private chat
        {
            'update_id': 1,
            'edited_message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {
                'chat': DEFAULT_TG_UPDATE_PAYLOAD['message']['chat'] | {'type': 'channel'},
            },
        },
        # Without message specified
        {
            'update_id': 1,
            'callback_query': {
                'id': 1,
                'data': '-',
                'from': DEFAULT_TG_UPDATE_PAYLOAD['message']['from'],
            },
        },
        # Non private chat
        {
            'update_id': 1,
            'callback_query': {
                'id': 1,
                'data': '-',
                'from': DEFAULT_TG_UPDATE_PAYLOAD['message']['from'],
                'message': DEFAULT_TG_UPDATE_PAYLOAD['message'] | {
                    'chat': DEFAULT_TG_UPDATE_PAYLOAD['message']['chat'] | {'type': 'channel'},
                },
            },
        },
    ],
)
@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_raise_on_process_tg_update_with_wrong_tg_update_object(wrong_update_payload):
    SessionModel.objects.create(
        tg_chat_id=DEFAULT_TG_CHAT_ID,
        tg_user_id=DEFAULT_TG_USER_ID,
        state_machine_locator=Locator(state_class_locator='/'),
    )

    router = Router()

    @router.register('/')
    class RootState(PrivateChatState):
        ...

    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    wrong_update = Update.parse_obj(wrong_update_payload)

    with state_machine.restore_session(tg_chat_id=DEFAULT_TG_CHAT_ID) as session:
        with pytest.raises(state_machine.IrrelevantTgUpdate):
            session.process_tg_update(wrong_update)


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_process_message_received():
    router = Router()
    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    @router.register('/')
    class RootState(PrivateChatState):
        pass

    RootState.process_message_received = MagicMock(return_value=None)

    message_received_update = Update.parse_obj({
        'update_id': 1,
        'message': {
            'message_id': 101,
            'from': {
                'id': DEFAULT_TG_USER_ID,
                'is_bot': False,
                'first_name': 'Иван Петров',
                'username': DEFAULT_TG_USERNAME,
            },
            'date': 0,
            'chat': {
                'id': DEFAULT_TG_CHAT_ID,
                'type': 'private',
            },
        },
    })

    with state_machine.restore_or_create_session_from_tg_update(message_received_update) as session:
        session.switch_to(Locator('/'))
        session.process_tg_update(message_received_update)
        assert RootState.process_message_received.called
        RootState.process_message_received.assert_called_with(
            PrivateChatMessageReceived.from_tg_update(message_received_update),
        )


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_process_message_edited():
    router = Router()
    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    @router.register('/')
    class RootState(PrivateChatState):
        pass

    RootState.process_message_edited = MagicMock(return_value=None)

    message_edited_update = Update.parse_obj({
        "update_id": 692509276,
        "edited_message": {
            "message_id": 3338,
            "from": {
                "id": 228593536,
                "is_bot": False,
                'first_name': 'Иван Петров',
                "username": DEFAULT_TG_USERNAME,
                "language_code": "en",
            },
            "chat": {
                "id": 228593536,
                'first_name': 'Иван Петров',
                "username": DEFAULT_TG_USERNAME,
                "type": "private",
            },
            "date": 1696877512,
            "edit_date": 1696877517,
            "text": "Hello!",
        },
    })

    with state_machine.restore_or_create_session_from_tg_update(message_edited_update) as session:
        session.switch_to(Locator('/'))
        session.process_tg_update(message_edited_update)
        assert RootState.process_message_edited.called
        RootState.process_message_edited.assert_called_with(
            PrivateChatMessageEdited.from_tg_update(message_edited_update),
        )


@override_settings(ROLLBAR=None)
@pytest.mark.django_db
def test_process_callback_query():
    router = Router()
    state_machine = PrivateChatStateMachine(
        router=router,
        session_model=SessionModel,
    )

    @router.register('/')
    class RootState(PrivateChatState):
        pass

    RootState.process_callback_query = MagicMock(return_value=None)

    callback_query_update = Update.parse_obj({
        "update_id": 692509267,
        "callback_query": {
            "id": "981801765129023398",
            "from": {
                "id": DEFAULT_TG_USER_ID,
                "is_bot": False,
                'first_name': 'Иван Петров',
                "username": DEFAULT_TG_USERNAME,
            },
            "message": {
                "message_id": 3327,
                "from": {
                    "id": 1613441681,
                    "is_bot": True,
                    "first_name": "Debug bot",
                    "username": "debug_bot",
                },
                "chat": {
                    "id": 228593536,
                    "username": DEFAULT_TG_USERNAME,
                    "type": "private",
                },
                "date": 1696874446,
                "text": "Main Menu",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {
                                "text": "Welcome message",
                                "callback_data": "welcome",
                            },
                        ],
                    ],
                },
            },
            "chat_instance": "-1534451349677707646",
            "data": "welcome",
        },
    })

    with state_machine.restore_or_create_session_from_tg_update(callback_query_update) as session:
        session.switch_to(Locator('/'))
        session.process_tg_update(callback_query_update)
        assert RootState.process_callback_query.called
        RootState.process_callback_query.assert_called_with(
            PrivateChatCallbackQuery.from_tg_update(callback_query_update),
        )
