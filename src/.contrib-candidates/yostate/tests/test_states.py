from ..states import BaseState


def test_state_ignores_unknown_args():
    state = BaseState(
        state_class_locator='/',
        extra_argument=1,
    )
    assert not hasattr(state, 'extra_argument')
