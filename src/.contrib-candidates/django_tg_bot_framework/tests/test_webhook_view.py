from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Any, Generator
from unittest.mock import MagicMock

import pytest
from pytest_httpx import HTTPXMock

from django.test import Client, override_settings
from django.urls import path

from tg_api import Update

from ..views import process_webhook_call


@contextmanager
def set_contextvar(contextvar: ContextVar[Any], value: Any) -> Generator[None, None, None]:
    var_token = contextvar.set(value)
    try:
        yield
    finally:
        contextvar.reset(var_token)


process_update_callable: ContextVar[Callable[[...], ...]] = ContextVar('process_update_callable')
process_error_callable: ContextVar[Callable[[...], ...]] = ContextVar(
    'process_error')


def call_process_update_callable(*args, **kwargs):
    return process_update_callable.get()(*args, **kwargs)


def call_process_error_callable(*args, **kwargs):
    return process_error_callable.get()(*args, **kwargs)


urlpatterns = [
    path(
        'webhook/',
        process_webhook_call,
        kwargs={
            'process_update': call_process_update_callable,
            'webhook_token': 'secret-webhook-token',
            'process_error': call_process_error_callable,
        },
    ),
    path(
        'webhook/token-unspecified/',
        process_webhook_call,
        kwargs={
            'process_update': call_process_update_callable,
            'process_error': call_process_error_callable,
        },
    ),
    path(
        'webhook/token-in-null/',
        process_webhook_call,
        kwargs={
            'process_update': call_process_update_callable,
            'webhook_token': None,
            'process_error': call_process_error_callable,
        },
    ),
    path(
        'webhook/token-in-empty-string/',
        process_webhook_call,
        kwargs={
            'process_update': call_process_update_callable,
            'webhook_token': '',
            'process_error': call_process_error_callable,
        },
    ),
    path(
        'webhook/custom-get-param/',
        process_webhook_call,
        kwargs={
            'process_update': call_process_update_callable,
            'webhook_token': 'secret-webhook-token',
            'token_get_params': ['custom-token'],
            'process_error': call_process_error_callable,
        },
    ),
]

request_payload_sample = {
    'update_id': 1,
    'message': {
        'message_id': 101,
        'from': {
            'id': 4114,
            'is_bot': False,
            'first_name': 'Иван Петров',
            'username': 'ivan_petrov',
        },
        'date': 0,
        'chat': {
            'id': 90001,  # noqa A003
            'type': 'private',  # noqa A003
        },
    },
}


@override_settings(ROOT_URLCONF=__name__)
def test_success(
    httpx_mock: HTTPXMock,
):
    process_update = MagicMock(return_value=None)
    expected_update = Update.parse_obj(request_payload_sample)

    with set_contextvar(process_update_callable, process_update):

        client = Client(headers={
            'X-Telegram-Bot-Api-Secret-Token': 'secret-webhook-token',
        })

        response = client.post(
            '/webhook/',
            request_payload_sample,
            content_type='application/json',
        )
        assert response.status_code == 200
        process_update.assert_called_once_with(expected_update)

    # TODO проверить, что отсутствует вызов logger.exception или logger.warning


@override_settings(ROOT_URLCONF=__name__)
def test_reject_unauthorized():
    client = Client()
    response = client.post(
        '/webhook/',
        {'update_id': 1},
        content_type='application/json',
    )
    assert response.status_code == 403
    assert response.json()['error'] == 'Invalid secret token.'


@override_settings(ROOT_URLCONF=__name__)
def test_reject_invalid_update():
    client = Client(headers={
        'X-Telegram-Bot-Api-Secret-Token': 'secret-webhook-token',
    })

    response = client.post(
        '/webhook/',
        {},
        content_type='application/json',
    )
    assert response.status_code == 400
    assert response.json()['error'] == 'Invalid update object format.'
    assert response.json()['details'] == [
        {
            'loc': ['update_id'],
            'msg': 'field required',
            'type': 'value_error.missing',
        },
    ]


@pytest.mark.parametrize(
    "webhook_url",
    [
        '/webhook/token-unspecified/',
        '/webhook/token-in-null/',
        '/webhook/token-in-empty-string/',
    ],
)
@override_settings(ROOT_URLCONF=__name__)
def test_disabling_webhook_token_check(webhook_url: str):
    process_update = MagicMock(return_value=None)
    client = Client()

    with set_contextvar(process_update_callable, process_update):
        response = client.post(
            webhook_url,
            request_payload_sample,
            content_type='application/json',
        )
        assert response.status_code == 200
        process_update.assert_called_once()


@pytest.mark.parametrize(
    "webhook_url",
    [
        '/webhook/?telegram_bot_api_secret_token=secret-webhook-token',
        '/webhook/custom-get-param/?custom-token=secret-webhook-token',
    ],
)
@override_settings(ROOT_URLCONF=__name__)
def test_webhook_authentication_by_get_param(webhook_url: str):
    process_update = MagicMock(return_value=None)
    client = Client()

    with set_contextvar(process_update_callable, process_update):
        webhook_url_without_get_params = webhook_url.split('?')[0]
        response = client.post(
            webhook_url_without_get_params,
            request_payload_sample,
            content_type='application/json',
        )
        assert response.status_code == 403

        response = client.post(
            webhook_url,
            request_payload_sample,
            content_type='application/json',
        )
        assert response.status_code == 200
        process_update.assert_called_once()

# TODO test_ignore_non_json_request():

# TODO test_logs_invalid_update_object_format():

# TODO def test_webhook_response_200_on_handler_failure():

# TODO def test_handler_timeout_limitation():
