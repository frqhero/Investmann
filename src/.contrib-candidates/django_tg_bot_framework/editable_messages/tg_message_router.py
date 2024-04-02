from .renderers import MessageSeriesRequests
from yostate import Router, Route
from mysent import (
    Message,
    MessageRouter,
    MessageLocator,
)


class EditableMessagesRouter(MessageRouter):

    def render(
        self,
        locator: MessageLocator,
        context: dict | None = None,
        *,
        language: str = None,
    ) -> MessageSeriesRequests:
        return super().render(locator, context, language=language)

    def fill_message_router_from_states(self, router: Router) -> None:
        for state_class_locator, route in router.items():
            messages_contracts = self._get_messages_contracts(route)
            for series_name, message_contract in messages_contracts.items():
                locator = MessageLocator(
                    state_class_locator,
                    series_name,
                )
                self.register(locator, message_contract)

    @staticmethod
    def _get_messages_contracts(route: Route) -> dict[str, Message]:
        if editable_messages := getattr(route.state_class, 'EditableMessages', None):
            messages_contracts = editable_messages.__dict__
        else:
            messages_contracts = getattr(route.state_class, '_editable_messages', {})

        return {
            name: editable_message
            for name, editable_message in messages_contracts.items()
            if isinstance(editable_message, Message)
        }
