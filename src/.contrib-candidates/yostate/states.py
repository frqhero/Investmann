from functools import cached_property
from typing import Any

from pydantic import BaseModel, Field

from .locators import Locator, FrozenLocator


class BaseState(BaseModel):
    """Base class for all states of state machine.

    Fill free to inherite custom state class from BaseState with adding new attributes to Pydantic model scheme.
    """

    state_class_locator: str = Field(
        description='Path-like string specifies how to find required State class. '
                    'Will be initialized by router on state instance creation.',
    )

    class Config:
        allow_mutation = False
        validate_all = True  # default values should be validated too
        extra = 'ignore'
        keep_untouched = (cached_property,)

    def enter_state(self) -> Locator | None:
        """Run any custom logic on state enter.

        Can return state object to force state machine switching to another state.
        """
        pass

    async def aenter_state(self) -> Locator | None:
        """Run any custom logic on state enter.

        Can return state object to force state machine switching to another state.
        """
        pass

    def exit_state(self, state_class_transition: bool) -> None:
        """Run any custom logic on state exit.

        State machine switching to another state is not available from this method.
        """
        pass

    async def aexit_state(self, state_class_transition: bool) -> None:
        """Run any custom logic on state exit.

        State machine switching to another state is not available from this method.
        """
        pass

    def process(self, event: Any) -> Locator | None:
        """Run any custom logic to process event.

        Can return state object to force state machine switching to another state.
        """
        pass

    async def aprocess(self, event: Any) -> Locator | None:
        """Run any custom logic to process event.

        Can return state object to force state machine switching to another state.
        """
        pass

    @cached_property
    def locator(self) -> Locator:
        return FrozenLocator(
            state_class_locator=self.state_class_locator,
            params=self.dict(
                exclude={'state_class_locator'},
                by_alias=True,
                exclude_defaults=True,  # Make locators shorter
            ),
        )
