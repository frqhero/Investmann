from typing import Any, Type

from ..router import Router, StateDecoratorType, Locator
from ..states import BaseState
from ..sync_crawler import Crawler


def test_simple_logging_sync_decorator():
    process_calls_log = []

    def log_process_calls(state_class: Type[BaseState]) -> StateDecoratorType:
        class WrappedStateClass(state_class):
            def process(self, event: Any) -> BaseState | None:
                process_calls_log.append(event)
                return super().process(event=event)
        return WrappedStateClass

    router = Router(decorators=[log_process_calls])

    @router.register('/', title='Корневое состояние бота')
    class RootState(BaseState):
        pass

    @router.register('/start/')
    class StartState(BaseState):
        pass

    crawler = Crawler(router=router)
    crawler.restore(Locator('/'))
    crawler.process('first_event')
    crawler.switch_to(Locator('/start/'))
    crawler.process('second_event')

    assert process_calls_log == [
        'first_event',
        'second_event',
    ]
