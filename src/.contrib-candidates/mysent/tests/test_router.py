import pytest

from ..exceptions import MYSentRouterError
from ..message_class import Message, Button, MessageLocator


def test_registration_of_message_contract(mock_message_router):
    message_contract = Message(sense='Приветствие!')
    locator = MessageLocator('/', 'Hello')
    mock_message_router.register(locator, message_contract)

    assert list(mock_message_router.items()) == [(locator, message_contract)]
    assert message_contract.renderers == mock_message_router.renderers
    assert message_contract.locator == locator


def test_already_registered(mock_message_router):
    message_contract = Message(sense='Приветствие')
    locator = MessageLocator('/', '/')
    mock_message_router.register(locator, message_contract)

    with pytest.raises(MYSentRouterError, match='already registered'):
        mock_message_router.register(locator, message_contract)

    with pytest.raises(MYSentRouterError, match='already registered'):
        mock_message_router[locator] = message_contract


def test_contract_not_found(mock_message_router):
    locator = MessageLocator('/', '/')
    with pytest.raises(MYSentRouterError, match='not found'):
        mock_message_router[locator]
    assert mock_message_router.get(locator) is None


def test_get_message(mock_message_router):
    message_contract = Message(
        sense='Приветствие',
        languages={'ru'},
    )
    locator = MessageLocator('/', '/')
    mock_message_router.register(locator, message_contract)
    assert mock_message_router.get(locator) == message_contract
    assert mock_message_router.get(locator, language='ru') == message_contract
    assert mock_message_router.get(locator, language='en') is None


def test_router_getters(mock_message_router):
    message_contract = Message(
        sense='Приветствие',
        placeholder='Hello world!',
        context_scheme={'foo': 'bar'},
        buttons=[
            Button('foo', action='bar'),
            Button('foo1', action='bar1', languages={'ru'}),
        ],
    )
    locator = MessageLocator('/', '/')
    mock_message_router.register(locator, message_contract)
    assert mock_message_router.get_sense(locator) == message_contract.sense
    assert mock_message_router.get_placeholder(locator) == message_contract.placeholder
    assert mock_message_router.get_context_scheme(locator) == message_contract.context_scheme
    assert mock_message_router.get_buttons_scheme(locator) == message_contract.buttons
    assert mock_message_router.get_buttons_scheme(locator, language='ru') == message_contract.buttons
    assert mock_message_router.get_buttons_scheme(locator, language='en') == message_contract.buttons[:1]
