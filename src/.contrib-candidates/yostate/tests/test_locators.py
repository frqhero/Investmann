from pydantic import ValidationError
import pytest

from ..locators import Locator


def test_pydantic_parse_obj():
    Locator.parse_obj({
        'state_class_locator': '/main-menu/',
    })


def test_protection_from_wrong_params_passing_to_locator():
    Locator('/profile/', params={'user_id': 10})

    with pytest.raises(ValidationError, match='user_id\n  extra fields not permitted'):
        Locator('/profile/', user_id=10)
