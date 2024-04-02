"""Run polling command."""
from argparse import ArgumentParser
from collections.abc import Callable, Generator
from contextlib import suppress
from functools import partial
from itertools import chain, repeat
from socket import gaierror
from textwrap import dedent
from time import sleep

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import autoreload
from django.utils.module_loading import import_string
from tg_api import SyncTgClient, Update, GetUpdatesRequest


def listen_to_updates(
    tg_bot_token: str,
    offset: int,
    limit: int,
    timeout: int,
    allowed_updates: list[str],
) -> Generator[Update, None, None]:
    """
    Listen to updates - sync.

    Yield updates in an endless loop
    """
    max_pause = 10
    pauses = chain((1, 3), repeat(max_pause))
    while True:
        with suppress(httpx.ReadTimeout), SyncTgClient.setup(tg_bot_token):
            try:
                tg_request = GetUpdatesRequest(
                    offset=offset,
                    limit=limit,
                    timeout=timeout,
                    allowed_updates=allowed_updates,
                )
                updates = tg_request.send().result
                for update in updates:
                    yield update
                    offset = update.update_id + 1
                pauses = chain((1, 3), repeat(max_pause))
            except (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.RemoteProtocolError,
                gaierror,
                ConnectionError,
            ):
                pause = next(pauses)
                sleep(pause)


def handle_polling(
    update_handler: Callable,
    tg_bot_token: str,
    offset: int,
    limit: int,
    timeout: int,
    allowed_updates: list[str],
):
    for update in listen_to_updates(
        tg_bot_token,
        offset,
        limit,
        timeout,
        allowed_updates,
    ):
        update_handler(update)


class Command(BaseCommand):
    """The management command class."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            'update_handler_path',
            help='A funtion path to process Telegram update (obligatory)',
            metavar='{update handler path}',
        )
        parser.add_argument(
            'tg_bot_token_path',
            help=dedent('''\
                        A path to the telegram_bot_token
                        in Django settings (obligatory)''',
                        ),
            metavar='{tg bot token path}',
        )
        parser.add_argument(
            '--timeout',
            help='Timeout in seconds for long polling. Default: 10.',
            type=int,
            default=10,
            metavar='{timeout}',
        )

        parser.add_argument(
            '--limit',
            help='Limits the number of updates to be retrieved. Default: 100.',
            type=int,
            default=100,
            metavar='{limit}',
        )

        parser.add_argument(
            '--offset',
            help='Identifier of the first update to be returned. Default: 1',
            type=int,
            default=1,
            metavar='{offset}',
        )

        parser.add_argument(
            '--allowed_updates',
            help=dedent('''\
                Update types.
                For example, specify 'message edited_channel_post'.
                default: all update types except chat_member.
                If not specified, the previous setting will be used.
                ''',
                        ),
            type=str,
            default=None,
            metavar='{allowed updates}',
            nargs='+',
        )

        parser.add_argument(
            '--reload',
            help='Reload on code change',
            action='store_true',
        )

    def handle(self, *args, **options) -> None:
        tg_bot_token_path = options['tg_bot_token_path']
        tg_bot_token = eval(
            f"settings.{tg_bot_token_path}", None, {'settings': settings},
        )
        polling_handler = partial(
            handle_polling,
            update_handler=import_string(options['update_handler_path']),
            tg_bot_token=tg_bot_token,
            offset=options['offset'],
            limit=options['limit'],
            timeout=options['timeout'],
            allowed_updates=options['allowed_updates'] or [],
        )
        if options['reload']:
            autoreload.run_with_reloader(polling_handler)
        polling_handler()
