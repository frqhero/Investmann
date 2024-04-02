import pytest

from ..message_class import Message, Button
from ..exceptions import MYSentContextError, MYSentMessageError
from ..renderers import render_from_placeholder


def test_sense_cleaning():
    editable_message = Message('   Приветствие!   ')
    assert editable_message.sense == 'Приветствие!'

    with pytest.raises(MYSentMessageError, match='Sense is empty'):
        Message('   ')


def test_render_method():
    editable_message = Message(
        'Hello message',
        placeholder='Hello {{ name }}!',
        renderers=[render_from_placeholder],
        context_scheme={'name': 'name'},
    )
    context = {'name': 'John Smith'}

    with pytest.raises(MYSentContextError, match='Context is not appropriate'):
        editable_message.render()

    assert editable_message.render(context) == 'Hello John Smith!'


@pytest.mark.parametrize(
    "has_buttons, button_languages, message_languages, error",
    [
        (True, None, None, False),
        (True, ['ru'], ['ru'], False),
        (True, ['en'], ['ru'], True),
        (True, ['en'], ['en', 'ru'], False),
        (True, ['en', 'ru'], ['ru'], True),
        (True, ['en', 'ru'], None, False),
        (True, None, ['ru'], False),
        (False, None, ['ru'], False),
        (False, None, None, False),
    ],
)
def test_languages(has_buttons, button_languages, message_languages, error):
    buttons = [
        Button(
            'Button',
            action='Do something',
            languages=button_languages,
        ),
    ] if has_buttons else None

    if error:
        with pytest.raises(MYSentMessageError, match='not appropriate with the message languages'):
            Message(
                'Message',
                buttons=buttons,
                languages=message_languages,
            )
    else:
        Message(
            'Message',
            buttons=buttons,
            languages=message_languages,
        )


@pytest.mark.parametrize(
    "buttons_actions, error",
    [
        (['test1'], False),
        (['test1', 'test2'], False),
        (['test1', 'test1'], True),
        (['test2', 'test1', 'test1'], True),
        ([], False),
    ],
)
def test_buttons(buttons_actions, error):
    buttons = [
        Button('Button', action=action)
        for action in buttons_actions
    ]
    if error:
        with pytest.raises(MYSentMessageError, match='Repeated button action'):
            Message('Message', buttons=buttons)
    else:
        Message('Message', buttons=buttons)


def test_renderers_order():
    null_renderer = lambda x, y: None  # noqa E731
    normal_renderer = lambda x, y: 'Normal'  # noqa E731

    editable_message = Message(
        sense='Hello {{ name }}!',
        renderers=[null_renderer, normal_renderer],
    )

    assert editable_message.render() == 'Normal'

    editable_message = Message(
        sense='Hello {{ name }}!',
        renderers=[normal_renderer, null_renderer],
    )

    assert editable_message.render() == 'Normal'
