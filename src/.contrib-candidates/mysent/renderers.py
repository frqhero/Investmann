from typing import Callable, Any

from .message_class import Message
from .templater import render_chevron_template


def render_from_placeholder(
    message_contract: Message,
    context: dict,
) -> str:
    return render_chevron_template(message_contract.placeholder, context)


class BaseRenderer:
    def __init__(
        self,
        *,
        template_engine: Callable = render_chevron_template,
        empty_value=None,
        use_placeholder: bool = False,
    ):
        self.use_placeholder = use_placeholder
        self.process_templating = template_engine
        self.empty_value = empty_value

    def __call__(self, message_contract: Message, context: dict):
        rendered_message = self.render_message(message_contract, context)
        if (
            rendered_message is None
            and self.use_placeholder
            and message_contract.placeholder is not None
        ):
            rendered_message = self.render_placeholder(message_contract, context)

        if rendered_message is None:
            rendered_message = self.empty_value
        return rendered_message

    def render_message(self, message_contract: Message, context: dict) -> Any:
        pass

    def render_placeholder(self, message_contract: Message, context: dict) -> Any:
        pass
