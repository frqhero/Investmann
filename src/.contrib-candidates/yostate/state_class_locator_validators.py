import re
import string
from typing import Callable

STATE_CLASS_LOCATOR_REGEXP = re.compile(r"^/([a-z0-9_\-]+/)*$")


StateClassLocatorValidator = Callable[str, str]


def validate_state_class_locator(value: str) -> str:
    """Проверяет Локатор класса состояний на соответствие принятому соглашению по наименованию.

    Проверяет Локатор класса состояний по максимально строгим правилам:
    - только ASCII символы
    - только нижний регистр
    - начинается и заканчивается слэшом `/`
    - без пробельных символов

    Функция только следит за соответствием, но не пытается сама нормализовать значение.
    """
    value = str(value)

    if not value.startswith('/'):
        raise ValueError(
            f'Wrong state class locator string format {value!r}. Leading slash symbol `/` is absent.',
        )

    if not value.endswith('/'):
        raise ValueError(
            f'Wrong state class locator string format {value!r}. Trailing slash symbol `/` is absent.',
        )

    if ' ' in value:
        raise ValueError(
            f'Wrong state class locator string format {value!r}. '
            'Whitespace symbols are found. Use dashes and underscores instead.',
        )

    found_uppercase_symbols = set(value) & set(string.ascii_uppercase)
    if set(value) & set(string.ascii_uppercase):
        raise ValueError(
            f'Wrong state class locator string format {value!r}. '
            f'Uppercase symbols are found: {found_uppercase_symbols!r}.',
        )

    allowed_symbols = f'{string.ascii_lowercase}{string.digits}_-/'
    prohibited_symbols = set(value) - set(allowed_symbols)

    if prohibited_symbols:
        raise ValueError(
            f'Wrong state class locator string format {value!r}. '
            'Prohibited symbols are found: {prohibited_symbols!r}.',
        )

    if not STATE_CLASS_LOCATOR_REGEXP.match(value):
        raise ValueError(
            f'Wrong state class locator string format {value!r}. Check out STATE_CLASS_LOCATOR_REGEXP.',
        )

    return value
