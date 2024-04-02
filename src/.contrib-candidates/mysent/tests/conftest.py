from typing import Any

import pytest

from .. import BaseRenderer, Message, MessageRouter


@pytest.fixture(scope='function')
def mock_message_router():
    class MockRenderer(BaseRenderer):
        def render_message(self, message_contract: Message, context: dict) -> Any:
            if message_contract.sense != 'no sense':
                return self.process_templating(message_contract.sense, context)

        def render_placeholder(self, message_contract: Message, context: dict) -> Any:
            return self.process_templating(message_contract.placeholder, context)

    return MessageRouter(
        MockRenderer(use_placeholder=True),
    )
