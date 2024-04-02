from contextvars import ContextVar, Token
from contextlib import contextmanager
from typing import TypeVar

from django.db import models
from django.utils import timezone

from ..locator_field import LocatorField

# Generic variable that can be 'AbstractPrivateChatSessionModel', or any subclass.
PrivateChatSessionModel = TypeVar('PrivateChatSessionModel', bound='AbstractPrivateChatSessionModel')


class AbstractPrivateChatSessionModel(models.Model):
    tg_chat_id = models.BigIntegerField(
        'Id чата в Tg',
        unique=True,
        db_index=True,
        help_text='Id чата в Tg, где пользователь общается с ботом.',
    )

    tg_user_id = models.BigIntegerField(
        'Id юзера в Tg',
        db_index=True,
        help_text=(
            'Id пользователя Telegram, с которым общается чат-бот. '
            'С одним пользователем может вестись сразу несколько чатов, каждому -- своя сессия чат-бота.<br>'
            'Пример значения: <code>123456789</code>.<br>'
            'Чтобы узнать ID пользователя, перешлите сообщение пользователя боту '
            '<a href="https://t.me/userinfobot">@userinfobot</a>.'
        ),
    )

    state_machine_locator = LocatorField(
        'Cостояние',
        null=True,
        blank=True,
        help_text=(
            'Локатор состояния, в котором сейчас находится чат с пользователем. Заполняется автоматически. '
            'Используется стейт-машиной.<br>'
            'Пример значения: <code>{"state_class_locator": "/start-menu/"}</code>.<br>'
            'В поле хранится объект JSON в формате локатора из библиотеки '
            '<a href="https://pypi.org/project/yostate/">yostate</a>: '
            'атрибут <code>state_class_locator</code> указывает локатор класса состояния и похож на часть адреса URL, '
            'атрибут <code>params</code> задаёт параметры состояния.'
        ),
    )

    last_update_tg_username = models.CharField(
        'Ник юзера Tg',
        max_length=50,
        blank=True,
        db_index=True,
        help_text=(
            'Имя пользователя в Telegram. Используется для поиска человека в базе данных по его нику в Telegram. '
            'Заполняется автоматически. <br>'
            'Имя пользователя хранится без старового символа <code>@</code>, например: <code>ivan-petrov</code>. '
            'Поле может быть пустым, если у пользователя не указан Telegram username.'
        ),
    )

    last_update_language_code = models.CharField(
        'Языковой код юзера Tg',
        max_length=8,
        blank=True,
        db_index=True,
        help_text=(
            'Языковой код установленный у пользователя в телеграмме.'
        ),
    )

    created_at = models.DateTimeField(
        'Когда создана',
        db_index=True,
        default=timezone.now,
        help_text='Когда была создана сессия. Обычно, сессия создаётся при первом сообщении пользователя к чат-боту.',
    )

    interacted_at = models.DateTimeField(
        'Последнее взаимодействие',
        db_index=True,
        null=True,
        blank=True,
        help_text=(
            'Когда было последнее взаимодействие пользователя с чат-ботом. Обновляется автоматически.<br/>'
            'Не каждое событие в чате считается за взаимодействие. Например, если сообщение от чат-бота только '
            'было доставлено, то пользователь об этом может и знать. А вот если сообщение было прочитано -- то это '
            'уже считаем за взаимодействие.'
        ),
    )

    _current_session_contextvar: ContextVar['AbstractPrivateChatSessionModel'] = ContextVar(
        '_current_session_contextvar',
    )

    class Meta:
        abstract = True
        verbose_name = "Сессия бота в приватном чате"
        verbose_name_plural = "Сессии бота в приватных чатах"
        unique_together = [
            ('tg_chat_id', 'tg_user_id'),
        ]

    def __str__(self):
        tg_username_label = self.last_update_tg_username or '???'
        return f'{self.id} сессия бота в приватном чате {self.tg_chat_id}, {tg_username_label}'

    @contextmanager
    def set_as_current(self):
        """Настраивает контекст на использование этого объекта БД в качестве текущего.

        Вызов метода `set_as_current` позволяет в дальнейшем получить доступ к этоу объекту БД через
        атрибут класса `current`.
        """
        var_token: Token = self._current_session_contextvar.set(self)
        try:
            yield
        finally:
            self._current_session_contextvar.reset(var_token)

    class NoCurrentSessionError(RuntimeError):
        pass

    class CurrentSessionSubtypeError(RuntimeError):
        pass

    @classmethod
    @property
    def current(cls: type[PrivateChatSessionModel]) -> PrivateChatSessionModel:
        """Get current session model object from context of raise exception."""
        value = cls._current_session_contextvar.get()

        if not value:
            raise AbstractPrivateChatSessionModel.NoCurrentSessionError(
                'Current context has no session model object selected. '
                'Has state machine initialization process been completed before?',
            )

        if not isinstance(value, cls):
            raise AbstractPrivateChatSessionModel.CurrentSessionSubtypeError(
                f'Expects current session be subtype of {cls}, but {type(value)} found in context.',
            )

        return value
