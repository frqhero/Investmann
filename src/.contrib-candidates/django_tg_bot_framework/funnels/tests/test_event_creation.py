from typing import Literal

import pytest
from pydantic import BaseModel, conint, ValidationError

from ..events import AbstractFunnelEvent


def test_event_type_subclassing():
    """Прикладной программист -- Добавить свой тип события: !func

    Через наследование: !story
    """  # noqa D400
    class ButtonPressed(AbstractFunnelEvent):
        pass

    event = ButtonPressed(
        tg_user_id=1,
        funnel_slug='default_funnel',
    )
    assert isinstance(event, AbstractFunnelEvent)


def test_event_type_virtual_subclassing():
    """Прикладной программист -- Добавить свой тип события: !func

    Через ABC.register вместо прямого наследования: !story
    """  # noqa D400
    class SpecialEvent(BaseModel):
        tg_user_id: conint(gt=0)
        funnel_slug: str

    AbstractFunnelEvent.register(SpecialEvent)

    assert issubclass(SpecialEvent, AbstractFunnelEvent)


def test_funnel_predefined():
    """Прикладной программист -- Добавить свой тип события: !func

    С предустановленной воронкой: !story
    """  # noqa D400
    class DefaultFunnelEvent(AbstractFunnelEvent):
        funnel_slug: str = 'default_funnel'

    DefaultFunnelEvent(tg_user_id=1)


def test_custom_event_attrs():
    """Прикладной программист -- Добавить свой тип события: !func

    Кастомные атрибуты: !story
    """  # noqa D400
    class ButtonPressed(AbstractFunnelEvent):
        button_slug: Literal['option_1', 'option_2']

    event = ButtonPressed(
        tg_user_id=1,
        funnel_slug='default_funnel',
        button_slug='option_1',
    )
    assert event.button_slug == 'option_1'


def test_failure_on_instantiation_with_unknown_event_attr():
    """Прикладной программист -- Создать событие: !func

    Неопознанные атрибуты: !story
        отказ:
            - Получил исключение
            - Вижу в описании исключения упоминание неопознанного атрибута события
    """  # noqa D400
    class MessageReceived(AbstractFunnelEvent):
        pass

    with pytest.raises(ValidationError, match='unknown_attr'):
        MessageReceived(
            tg_user_id=1,
            funnel_slug='default_funnel',
            unknown_attr='some-value',
        )


def test_instantiation_with_default_tg_user_id():
    """Прикладной программист -- Создать событие: !func

    Предустановленный tg_user_id: !story
    """  # noqa D400
    class MessageReceived(AbstractFunnelEvent):
        pass

    with AbstractFunnelEvent.set_default_tg_user_id(1):
        MessageReceived(funnel_slug='default_funnel')


def test_instantiation_with_funnel_selection():
    """Прикладной программист -- Создать событие: !func

    Со сменой дефолтной воронки: !story
    """  # noqa D400
    class MessageReceived(AbstractFunnelEvent):
        funnel_slug: str = 'default_funnel'

    event = MessageReceived(tg_user_id=1, funnel_slug='another_funnel')
    assert event.funnel_slug == 'another_funnel'
