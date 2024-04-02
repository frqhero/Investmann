from contextlib import suppress
import logging
from typing import Callable, Sequence

from pydantic import ValidationError

from django.db import transaction
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tg_api import Update


logger = logging.getLogger('django_tg_bot_framework')


@csrf_exempt
@require_http_methods(["POST"])
@transaction.non_atomic_requests
def process_webhook_call(
    request: HttpRequest,
    *,
    webhook_token: str | None = None,
    token_get_params: Sequence[str] = ('telegram_bot_api_secret_token',),
    process_update: Callable[[Update], None],
    process_error: Callable[[Exception], None],
) -> JsonResponse:
    logger.debug('Telegram webhook called')

    request_tokens_to_select = [
        *[request.GET.get(name) for name in token_get_params],
        request.META.get('HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'),
    ]

    request_token = None
    with suppress(StopIteration):
        request_token = next(token for token in request_tokens_to_select if token)

    if webhook_token and request_token != webhook_token:
        return JsonResponse({'error': 'Invalid secret token.'}, status=403)

    try:
        logger.debug('Receive JSON encoded Update object: %s', request.body)
        update = Update.parse_raw(request.body)
    except ValidationError as exc:
        logger.warning('Invalid update object format: %s', exc.json())
        return JsonResponse({
            'error': 'Invalid update object format.',
            'details': exc.errors(),
        }, status=400)

    try:
        process_update(update)
    except Exception as error:
        logger.exception('Webhook call finished with error')
        process_error(error)

    # Should response with status 200 always even if exception occurs to prevent bot be banned by Tg server
    return JsonResponse({'ok': 'POST request processed.'})
