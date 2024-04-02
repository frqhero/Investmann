from typing import Type, Callable, Sequence

from pydantic import ValidationError, validate_arguments, BaseModel

from .locators import Locator
from .exceptions import NotFoundStateClassLocatorError, LocatorParamsError
from .states import BaseState
from .state_class_locator_validators import validate_state_class_locator, StateClassLocatorValidator

StateDecoratorType = Callable[[Type[BaseState]], Type[BaseState]]


class Route(BaseModel):
    state_class_locator: str
    state_class: Type[BaseState]
    title: str = ''

    class Config:
        allow_mutation = False
        validate_all = True  # default values should be validated too


class Router(dict[str, Route]):
    """Index of registered state classes."""

    decorators: tuple[StateDecoratorType]
    state_class_locator_validators: tuple[StateClassLocatorValidator]

    @validate_arguments
    def __init__(
        self,
        decorators: Sequence[StateDecoratorType] | None = None,
        state_class_locator_validators: Sequence[Callable[str, str]] | None = (validate_state_class_locator, ),
    ):
        self.decorators = tuple(decorators) if decorators else tuple()
        self.state_class_locator_validators = state_class_locator_validators

    @validate_arguments
    def register(self, state_class_locator: str, *, title: str = ''):
        """Register a State with specified locator."""
        @validate_arguments
        def register_state_class(state_class: Type[BaseState]) -> Type[BaseState]:
            wrapped_state_class = state_class
            for decorator in reversed(self.decorators):
                wrapped_state_class = decorator(wrapped_state_class)

            cleaned_state_class_locator = self._validate_state_class_locator(state_class_locator)

            route = Route(
                state_class_locator=cleaned_state_class_locator,
                state_class=wrapped_state_class,
                title=title,
            )
            self[route.state_class_locator] = route

            return wrapped_state_class
        return register_state_class

    @validate_arguments
    def create_state(self, locator: Locator) -> BaseState:
        """Create new serializable State."""
        cleaned_state_class_locator = self._validate_state_class_locator(locator.state_class_locator)

        route = self.get(cleaned_state_class_locator, None)

        if not route:
            raise NotFoundStateClassLocatorError(
                f'Unknown state class locator {locator.state_class_locator!r} with '
                f'normalized value {cleaned_state_class_locator!r}',
            )

        try:
            return route.state_class.parse_obj(locator.params | {
                'state_class_locator': cleaned_state_class_locator,
            })
        except ValidationError as error:
            raise LocatorParamsError(f'Can`t create state for locator {locator}') from error

    def _validate_state_class_locator(self, value: str) -> str:
        for validate in self.state_class_locator_validators:
            value = validate(value)

        return value
