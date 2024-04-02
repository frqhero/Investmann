import pytest

from ..message_class import Message
from ..router import MessageLocator


@pytest.mark.parametrize(
    'sense, placeholder, context_scheme, context, result',
    [
        ('Hello {{ name }}!', '', {'name': 'User name'}, {'name': 'John Smith'}, 'Hello John Smith!'),
        ('no sense', 'Hello {{ name }}!', {'name': 'User name'}, {'name': 'John Smith'}, 'Hello John Smith!'),
        ('no sense', '', {'name': 'User name'}, {'name': 'John Smith'}, ''),
        ('no sense', '', None, None, ''),
        ('Hello {{ name }}!', '', None, None, 'Hello !'),
    ],
)
def test_base_renderer(mock_message_router, sense, placeholder, context_scheme, context, result):
    message = Message(
        sense,
        placeholder=placeholder,
        context_scheme=context_scheme,
    )
    mock_message_router.register(MessageLocator('/', 'render_from_sense'), message)
    assert message.render(context) == result
