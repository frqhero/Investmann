from collections.abc import Sequence
from typing import Callable, Any

from pydantic import BaseModel, Field, validator, root_validator

from .exceptions import MYSentContextError, MYSentMessageError
from .router import MessageLocator

RendererType = Callable[
    ['Message', dict],
    Any,
]

VariableName = str
VariableDescription = str


class Button(BaseModel):
    sense: str
    action: str
    languages: set[str] | None = Field(
        default=None,
        description='Языки кнопки. Если None, то кнопка работает со всеми языками в приложении.',
    )

    def __init__(
        self,
        sense: str,
        action: str,
        *,
        languages: set[str] = None,
    ):
        super().__init__(
            sense=sense,
            action=action,
            languages=languages,
        )


class Message(BaseModel):
    """Набор требований к редактируемым сообщениям, на которые рассчитывает код бота."""

    sense: str = Field(
        description='Смысл сообщения.',
    )
    namespace: str | None = Field(
        default=None,
        description='Пространство имён помогает избежать коллизий из-за похожих названий схем.',
    )
    name: str | None = Field(
        default=None,
        description='Идентификатор схемы внутри пространства имён.',
    )
    languages: set[str] | None = Field(
        default=None,
        description='Языки сообщения. Если None, то сообщение работает со всеми языками в приложении.',
    )
    placeholder: str | None = Field(
        default=None,
        description='Используется в случае, если не удалось подгрузить шаблон из источника данных.',
    )
    context_scheme: dict[VariableName, VariableDescription] = Field(
        default_factory=dict,
        description='Переменные контекста для шаблонизации.',
    )
    buttons: list[Button] = Field(
        default_factory=list,
        description='Требуемые кнопки.',
    )
    renderers: Sequence[RendererType] | None = Field(
        default=None,
        description='Рендереры, подготавливающие сообщение к использованию.',
    )

    class Config:
        validate_all = True
        validate_assignment = True

    def __init__(
        self,
        sense: str,
        *,
        namespace: str = None,
        name: str = None,
        languages: set[str] = None,
        placeholder: str = None,
        context_scheme: dict[VariableName, VariableDescription] = None,
        buttons: list[Button] = None,
        renderers: Sequence[RendererType] = None,
    ):
        super().__init__(
            sense=sense,
            namespace=namespace,
            name=name,
            languages=languages,
            placeholder=placeholder,
            context_scheme=context_scheme or {},
            buttons=buttons or [],
            renderers=renderers,
        )

    @property
    def locator(self):
        return MessageLocator(self.namespace, self.name)

    @validator('sense')
    def clean_sense(cls, value: str):  # noqa N805
        value = value.strip()
        if not value:
            raise MYSentMessageError('Sense is empty')
        return value

    @root_validator
    def validate_languages(cls, values: dict):  # noqa N805
        buttons = values.get('buttons')
        message_languages = values.get('languages')
        if not buttons or message_languages is None:
            return values

        for button in buttons:
            if button.languages is None or button.languages <= message_languages:
                continue
            raise MYSentMessageError(
                f'Error in message "{values["sense"]}". '
                f'One of the buttons has languages={button.languages} '
                f'which is not appropriate with the message languages={message_languages}',
            )
        return values

    @root_validator
    def validate_button_actions(cls, values: dict):  # noqa N805
        buttons = values.get('buttons')
        if not buttons:
            return values

        actions = set()
        for button in buttons:
            if button.action in actions:
                raise MYSentMessageError(
                    f'Error in message "{values["sense"]}". '
                    f'Repeated button action "{button.action}" ',
                )
            actions.add(button.action)
        return values

    def render(self, context: dict | None = None):
        context = context or {}
        if self.context_scheme.keys() != context.keys():
            raise MYSentContextError(
                'Context is not appropriate. '
                f'Expecting {self.context_scheme.keys()}, but {context.keys()} were given',
            )
        for renderer in self.renderers:
            result = renderer(self, context)
            if result is not None:
                return result

    def get_buttons(self, language: str = None):
        return [
            button
            for button in self.buttons
            if language is None or button.languages is None or language in button.languages
        ]
