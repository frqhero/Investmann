from typing import NamedTuple, Generator, TYPE_CHECKING, Optional, Any

from .exceptions import MYSentRouterError

if TYPE_CHECKING:
    from .message_class import Message, RendererType, Button


class MessageLocator(NamedTuple):
    # TODO Добавить валидацию name и namespace. Желательно в момент создания инстанции Message
    namespace: str
    name: str

    def __str__(self):
        return f'{self.namespace}::{self.name}'


class MessageRouter(dict[MessageLocator, 'Message']):

    def __init__(self, *renderers: 'RendererType'):
        if not renderers:
            raise MYSentRouterError('Renderers is not defined')
        super().__init__()
        self.renderers = renderers

    def __getitem__(self, locator: MessageLocator):
        try:
            return super().__getitem__(locator)
        except KeyError:
            raise MYSentRouterError(f'Message contract for locator {locator} not found.') from None

    def __setitem__(self, locator: MessageLocator, message_contract: 'Message'):
        if locator in self:
            raise MYSentRouterError(f'Message contract for locator {locator} is already registered.')
        message_contract.name = locator.name
        message_contract.namespace = locator.namespace
        message_contract.renderers = self.renderers
        super().__setitem__(locator, message_contract)

    def register(self, locator: MessageLocator, message_contract: 'Message') -> None:
        self[locator] = message_contract

    def render(self, locator: MessageLocator, context: dict = None, *, language: str = None) -> Any:
        message_contract = self.get(locator, language=language)
        if not message_contract:
            raise MYSentRouterError(f'Message contract for locator {locator}'
                                    f' and language {language} not found.')
        return message_contract.render(context)

    def get(self, locator: MessageLocator, *, language: str = None) -> Optional['Message']:
        message_contract = super().get(locator)
        if (
            language is None
            or message_contract and message_contract.languages is None
            or message_contract and language in message_contract.languages
        ):
            return message_contract

    def get_sense(self, locator: MessageLocator) -> str | None:
        if message_contract := self.get(locator):
            return message_contract.sense

    def get_placeholder(self, locator: MessageLocator) -> str | None:
        if message_contract := self.get(locator):
            return message_contract.placeholder

    def get_context_scheme(self, locator: MessageLocator) -> dict[str, str] | None:
        if message_contract := self.get(locator):
            return message_contract.context_scheme

    def get_buttons_scheme(self, locator: MessageLocator, *, language: str = None) -> list['Button'] | None:
        if message_contract := self.get(locator, language=language):
            return message_contract.get_buttons(language)

    def filter_by_language(self, language: str) -> Generator['Message', None, None]:
        yield from filter(
            lambda m: m.languages is None or language in m.languages,
            self.values(),
        )
