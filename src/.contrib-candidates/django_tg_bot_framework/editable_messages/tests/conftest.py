import pytest
from django.contrib.admin.sites import site as default_site

from mysent import Message, MessageLocator, Button
from ..admin import EditableMessagesAdmin
from ..models import TgMessageSeries, TgTextMessage, TgInlineButton
from ..renderers import DbTgRenderer
from ..tg_message_router import EditableMessagesRouter


@pytest.fixture()
def admin_site(pre_filled_db, pre_filled_message_router):
    class MockAdmin(EditableMessagesAdmin):
        message_router = pre_filled_message_router
        languages = {'ru': 'ru'}

    return MockAdmin(TgMessageSeries(), default_site)


@pytest.fixture()
def pre_filled_message_router():
    message_router = EditableMessagesRouter(
        DbTgRenderer(lambda: 1, lambda: 'ru'),
    )
    messages = [
        Message('missed'),
        Message('draft'),
        Message('active_empty'),
        Message(
            'normal',
            context_scheme={'foo': 'bar'},
            buttons=[Button('bar', action='foo')],
        ),
        Message(
            'missed_only_ru',
            context_scheme={'foo': 'bar'},
            buttons=[Button('bar', action='foo')],
            languages={'ru'},
        ),
        Message(
            'only_ru_button',
            context_scheme={'foo': 'bar'},
            buttons=[
                Button('bar', action='foo_ru', languages={'ru'}),
            ],
        ),
        Message(
            'missed_buttons',
            buttons=[Button('bar', action='foo')],
        ),
        Message(
            'missed_button_link',
            buttons=[Button('bar', action='foo')],
        ),
    ]

    for message in messages:
        message_router.register(
            MessageLocator('/', message.sense),
            message,
        )

    return message_router


@pytest.fixture()
def pre_filled_db():
    normal = TgMessageSeries(namespace='/', name='normal', language_code='ru')
    missed_only_ru = TgMessageSeries(namespace='/', name='missed_only_ru', language_code='en')
    only_ru_button_en = TgMessageSeries(namespace='/', name='only_ru_button', language_code='en')
    only_ru_button_ru = TgMessageSeries(namespace='/', name='only_ru_button', language_code='ru')
    draft = TgMessageSeries(namespace='/', name='draft', language_code='ru', draft=True)
    redundant = TgMessageSeries(namespace='/', name='redundant', language_code='ru')
    active_empty = TgMessageSeries(namespace='/', name='active_empty', language_code='ru')
    redundant_empty = TgMessageSeries(namespace='/', name='redundant_empty', language_code='ru')
    redundant_draft = TgMessageSeries(namespace='/', name='redundant_draft', language_code='ru', draft=True)
    missed_buttons = TgMessageSeries(namespace='/', name='missed_buttons', language_code='ru')
    missed_buttons_link = TgMessageSeries(namespace='/', name='missed_button_link', language_code='ru')

    TgMessageSeries.objects.bulk_create([
        normal,
        missed_only_ru,
        only_ru_button_en,
        only_ru_button_ru,
        draft,
        redundant,
        missed_buttons,
        active_empty,
        redundant_empty,
        redundant_draft,
        missed_buttons_link,
    ])

    TgTextMessage.objects.bulk_create([
        TgTextMessage(text='message_normal', series=normal, message_order=1),
        TgTextMessage(text='message_missed_only_ru', series=missed_only_ru),
        TgTextMessage(text='only_ru_button_en', series=only_ru_button_en, message_order=1),
        TgTextMessage(text='only_ru_button_ru', series=only_ru_button_ru, message_order=1),
        TgTextMessage(text='message_draft', series=draft),
        TgTextMessage(text='message_redundant', series=redundant),
        TgTextMessage(text='message_missed_buttons', series=missed_buttons),
        TgTextMessage(text='message_missed_buttons_link', series=missed_buttons_link, message_order=0),
    ])

    TgInlineButton.objects.bulk_create([
        TgInlineButton(
            text='Normal button',
            callback_data='foo',
            message_number=1,
            row=1,
            position_in_row=1,
            series=normal,
        ),
        TgInlineButton(
            text='URL button',
            url='http://test.ru',
            message_number=1,
            row=1,
            position_in_row=2,
            series=normal,
        ),
        TgInlineButton(
            text='Bad button',
            callback_data='foo_ru',
            message_number=1,
            row=1,
            position_in_row=1,
            series=only_ru_button_ru,
        ),
        TgInlineButton(
            text='Bad button',
            callback_data='foo_ru',
            message_number=1,
            row=1,
            position_in_row=1,
            series=only_ru_button_ru,
        ),
        TgInlineButton(
            text='Only ru button',
            callback_data='foo',
            message_number=1,
            row=1,
            position_in_row=1,
            series=missed_buttons_link,
        ),
    ])
