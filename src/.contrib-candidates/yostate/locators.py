from typing import Any

from pydantic import BaseModel, Field


class Locator(BaseModel):
    state_class_locator: str

    params: dict[str, Any] = Field(default_factory=dict)

    class Config:
        allow_mutation = True
        validate_assignment = True
        validate_all = True  # default values should be validated too
        extra = 'forbid'

    def __init__(self, *args, **kwargs):
        """Like common pydantic.BaseModel init method with support of positional argument `state_class_locator`.

        Full compatabilite with pydantic.BaseModel.__init__ method is provided.
        """
        if len(args) == 1:
            super().__init__(state_class_locator=args[0], **kwargs)
        else:
            super().__init__(*args, **kwargs)


class FrozenLocator(Locator):
    class Config:
        allow_mutation = False
