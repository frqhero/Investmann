from typing import Any

from yostate import Locator, BaseState

from .events import (
    PrivateChatMessageReceived,
    PrivateChatMessageEdited,
    PrivateChatCallbackQuery,
)


class PrivateChatState(BaseState):
    def process_message_received(self, message: PrivateChatMessageReceived) -> Locator | None:
        pass

    def process_message_edited(self, message: PrivateChatMessageEdited) -> Locator | None:
        pass

    def process_callback_query(self, callback_query: PrivateChatCallbackQuery) -> Locator | None:
        pass

    def process(self, event: Any) -> Locator | None:
        """Handle events of PrivateChatStateMachine.

        Can return locator to switch state machine crawler to another state.
        """
        match event:
            case PrivateChatMessageReceived():
                return self.process_message_received(event)
            case PrivateChatMessageEdited():
                return self.process_message_edited(event)
            case PrivateChatCallbackQuery():
                return self.process_callback_query(event)

        return super().process(event)
