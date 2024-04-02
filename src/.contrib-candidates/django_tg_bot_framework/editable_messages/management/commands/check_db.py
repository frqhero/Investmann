from argparse import ArgumentParser
from typing import Type

from django.core.management import BaseCommand
from django.contrib.admin.sites import site as default_site
from django.utils.module_loading import import_string

from mysent import MessageRouter
from ...exceptions import EditableMessagesDbCheckingError
from ...db_checker import DbStatement
from ...models import TgMessageSeries


class Command(BaseCommand):
    redundant_message = ''
    error_message = ''

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            'message-router',
            default=None,
            nargs='?',
            help='Dotted path to the message router instance',
        )
        parser.add_argument(
            '--default-admin-site',
            dest='default_admin_site',
            action='store_true',
            help='Message router will be found in the default admin site automatically',
        )
        parser.add_argument(
            'lang',
            help='Check only for specific language',
        )
        parser.add_argument(
            '--raise',
            action='store_true',
            help='Raise exception if checkin have failed',
        )

    def handle(self, *args, **options) -> str | None:
        message_router = get_message_router(options)

        language_codes = [lang.strip() for lang in options['lang'].split(',') if lang]
        db_statement = DbStatement(message_router, language_codes)

        for language in language_codes:
            self.get_redundant_message(language, db_statement)
            self.get_error_message(language, db_statement)

        if not self.error_message:
            return self.redundant_message or 'No problems detected in the database.'

        if options['raise']:
            raise EditableMessagesDbCheckingError(
                '\n' + self.error_message + '\n\n' + self.redundant_message + '\n',
            )

        return self.error_message + '\n\n' + self.redundant_message

    def get_redundant_message(self, language: str, db_statement: DbStatement):
        redundant_messages = []
        if redundant_locators := db_statement.redundant.get(language):
            redundant_locators_representations = [
                str(locator)
                for locator in redundant_locators
            ]
            redundant_messages.append(
                f'Redundant messages for {language}:\n' + '\n'.join(redundant_locators_representations),
            )
        self.redundant_message = '\n'.join(redundant_messages)

    def get_error_message(self, language: str, db_statement: DbStatement):
        representations = []
        draft_locators = db_statement.drafts.get(language, set())
        missed_locators_representation = [
            str(locator) + ' - Has draft!' if locator in draft_locators else str(locator)
            for locator in db_statement.missed.get(language, set())
        ]
        if missed_locators_representation:
            representations.append(
                f'Missing messages for {language}:\n' + '\n'.join(missed_locators_representation),
            )

        empty_locators = {
            locator
            for locator in db_statement.empty.get(language, set())
            if locator in db_statement.active.get(language, set())
        }
        if empty_locators:
            empty_locators_representation = [
                str(locator)
                for locator in empty_locators
                if locator in db_statement.active.get(language, set())
            ]
            representations.append(
                f'\nEmpty messages for {language}:\n' + '\n'.join(empty_locators_representation),
            )

        if missed_buttons := db_statement.missed_buttons.get(language, dict()):
            missed_buttons_representation = [
                f'{locator}  {callbacks=}'
                for locator, callbacks in missed_buttons.items()
            ]
            representations.append(
                f'\nMissed buttons for {language}:\n' + '\n'.join(missed_buttons_representation),
            )

        if representations:
            self.error_message = '\n'.join(representations)


def get_message_router(options: dict) -> MessageRouter:
    if options['message-router']:
        return import_string(options['message-router'])
    elif options['default_admin_site']:
        return get_message_router_from_default_admin_site()
    raise EditableMessagesDbCheckingError(
        'You must define path to the message router instance or user "--default-admin-site"',
    )


def get_message_router_from_default_admin_site(
    series_model: Type[TgMessageSeries] = TgMessageSeries,
) -> MessageRouter:
    for model, admin_class in default_site._registry.items():
        if issubclass(model, series_model):
            return admin_class.message_router
