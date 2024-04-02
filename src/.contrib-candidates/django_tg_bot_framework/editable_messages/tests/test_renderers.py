import pytest
import tg_api

from mysent import (
    Message,
    Button,
    MYSentContextError,
    MessageLocator,
)
from ..renderers import MessageSeriesRequests, MockTgRenderer
from ..tg_message_router import EditableMessagesRouter


@pytest.mark.django_db
def test_db_tg_renderer(pre_filled_db, pre_filled_message_router):
    context = {'foo': 'bar'}
    message_contract = pre_filled_message_router[MessageLocator('/', 'normal')]
    rendered_message_request = message_contract.render(context)
    assert isinstance(rendered_message_request, MessageSeriesRequests)
    assert len(rendered_message_request) == 1
    first_message_request, *_ = rendered_message_request
    assert first_message_request.text == 'message_normal'

    keyboard = first_message_request.reply_markup.inline_keyboard
    assert isinstance(first_message_request.reply_markup, tg_api.InlineKeyboardMarkup)
    assert len(keyboard) == 1
    assert len(keyboard[0]) == 2
    main_button, url_button = keyboard[0]
    assert main_button.callback_data == 'foo'
    assert main_button.text == 'Normal button'
    assert main_button.url == ''
    assert url_button.text == 'URL button'
    assert url_button.callback_data == ''
    assert url_button.url == 'http://test.ru'


def test_mock_renderer():
    message_router = EditableMessagesRouter(
        MockTgRenderer(lambda: 1, lambda: 'ru'),
    )
    message_contract = Message(
        sense='Hello message',
        placeholder='Hello {{ name }}!',
        context_scheme={'name': 'name'},
        buttons=[Button('Main menu button', action='main')],
    )
    message_router.register(MessageLocator('/', 'welcome'), message_contract)

    with pytest.raises(MYSentContextError, match='Context is not appropriate'):
        message_contract.render()

    context = {'name': 'John Smith'}
    rendered_message_request = message_contract.render(context)
    assert isinstance(rendered_message_request, MessageSeriesRequests)
    assert len(rendered_message_request) == 1
    assert rendered_message_request[0].text == 'Hello John Smith!'

    first_message_request, *_ = rendered_message_request
    main_button = first_message_request.reply_markup.inline_keyboard[0][0]
    assert main_button.callback_data == 'main'
