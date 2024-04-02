from itertools import count
import logging
from typing import final, Any

from pydantic import validate_arguments

from .states import BaseState
from .router import Router, Locator
from .exceptions import (
    TooLongTransitionError,
    LocatorError,
    DetachedCrawlerError,
)

logger = logging.getLogger('yostate')


@final
class Crawler:
    router: Router
    current_state: BaseState | None = None
    max_transition_length: int = 20

    @validate_arguments
    def __init__(
        self,
        router: Router,
        max_transition_length: int = max_transition_length,
    ):
        """Инициализирует краулер.

        Аргумент `max_transition_length` настраивает защиту от зацикливания. Он ограничивает максимальную длину
        непрерывной цепочки переходов между состояниями.
        """
        self.router = router
        self.max_transition_length = max_transition_length

    @validate_arguments
    def restore(self, locator: Locator, ignore_errors: bool = False):
        """Восстанавливает положение краулера в прежнем состоянии.

        Используйте метод `restore` чтобы восстановить положение краулера в том состоянии, где он ранее прервал
        свою работу.
        Вызов метода `restore` отличается от `switch_to` тем, что не приводит к запуску кода в методе
        `BaseState.enter_state` и не запускает процесс переходов по состояниям.
        """
        try:
            self.current_state = self.router.create_state(locator)
        except LocatorError:
            if not ignore_errors:
                raise
            logger.warning('Crawler restore failed for locator %s', locator)

    def detach(self):
        self.current_state = None

    def process(self, event: Any) -> None:
        """Обрабатывает поступившее событие."""
        if not self.attached:
            raise DetachedCrawlerError('Crawler is not attached yet')

        next_locator = self.current_state.process(event=event)

        if next_locator:
            self.switch_to(next_locator)

    @validate_arguments
    def switch_to(self, locator: Locator) -> None:  # noqa CCR001
        """Переводит краулер в новое состояние и следует далее по цепочке переходов до упора.

        В краулер встроена защиты от зацикливания. Она ограничивает максимальную длину цепочки переходов.
        """
        next_state = self.router.create_state(locator)

        counter = count(1)

        prev_state = self.current_state

        for transition_length in counter:
            if transition_length > self.max_transition_length:
                raise TooLongTransitionError(
                    f'Transition length limit of {self.max_transition_length} is exceeded.',
                )

            logger.debug(
                'State %s → %s.',
                prev_state and prev_state.state_class_locator,
                next_state.state_class_locator,
            )
            logger.debug('    Old: %s', prev_state)
            logger.debug('    New: %s', next_state)

            state_class_transition = type(prev_state) != type(next_state)

            if prev_state:
                prev_state.exit_state(state_class_transition=state_class_transition)

            next_next_locator = next_state.enter_state()
            if not next_next_locator:
                break

            next_next_state = self.router.create_state(next_next_locator)
            prev_state, next_state = next_state, next_next_state

        self.current_state = next_state

    @property
    def attached(self) -> bool:
        return bool(self.current_state)
