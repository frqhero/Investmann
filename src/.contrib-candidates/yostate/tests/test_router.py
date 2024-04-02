import pytest

from ..exceptions import NotFoundStateClassLocatorError
from ..router import Router, Locator
from ..states import BaseState


def test_locator_usage():
    router = Router()

    @router.register('/some/state/', title='Некий класс состояний бота')
    class SomeState(BaseState):
        page_number: int = 10

    first_found_state = router.create_state(Locator('/some/state/'))
    assert first_found_state == SomeState(
        state_class_locator='/some/state/',
        page_number=10,
    )

    second_found_state = router.create_state(Locator('/some/state/', params={'page_number': 9}))
    assert second_found_state == SomeState(
        state_class_locator='/some/state/',
        page_number=9,
    )


def test_state_class_registration():
    router = Router()

    @router.register('/', title='Корневое состояние бота')
    class RootState(BaseState):
        pass

    assert router['/'].state_class_locator == '/'
    assert router['/'].state_class == RootState
    assert router['/'].title == 'Корневое состояние бота'

    assert router.create_state(Locator('/'))


def test_locate_with_params():
    router = Router()

    @router.register('/menu/', title='Меню')
    class PromptState(BaseState):
        message_id: int

    locator = Locator('/menu/', params={'message_id': 10})
    assert router.create_state(locator)


def test_unknown_state_class_locator():
    router = Router()
    locator = Locator('/menu/', params={'message_id': 10})
    with pytest.raises(NotFoundStateClassLocatorError):
        router.create_state(locator)


@pytest.mark.parametrize("state_class_locator,reason", [
    ('without-leading-slash', 'Leading slash symbol'),
    ('/without-trailing-slash', 'Trailing slash symbol'),
    ('/with whitespace/', 'Whitespace symbols are found'),
    ('/WithUpperCase/', 'Uppercase symbols are found'),
    ('/without|prohibited|symbols/', 'Prohibited symbols are found'),
    ('//', 'Check out STATE_CLASS_LOCATOR_REGEXP.'),
])
def test_validate_state_class_locator_on_registration(state_class_locator: str, reason: str):
    router = Router()
    with pytest.raises(ValueError, match=reason):
        @router.register(state_class_locator)
        class SomeState(BaseState):
            pass


def test_failute_on_state_class_registration_without_inheritance_from_base_state():
    router = Router()
    with pytest.raises(ValueError, match='BaseState'):
        @router.register('/')
        class A():
            pass
