from contextlib import ExitStack, contextmanager
from functools import partial
import logging
from typing import final, Sequence, Type, Any, ContextManager, Callable

from pydantic import ValidationError, validate_arguments
from tg_api import Update, SyncTgClient
from yostate import Crawler, Locator, Router, LocatorError

from django.db import transaction
from django.conf import settings
from django.utils import timezone

from .models import AbstractPrivateChatSessionModel
from .events import (
    PrivateChatMessageReceived,
    PrivateChatMessageEdited,
    PrivateChatCallbackQuery,
)

logger = logging.getLogger('django_tg_bot_framework')

PrivateChatContextFunc = Callable[
    [],
    ContextManager[None],
]


@final
class ActivePrivateChatSession:
    session_db_object: AbstractPrivateChatSessionModel
    db_fields_pending_saves: set[str]
    crawler: Crawler

    def __init__(self, *, session_db_object, crawler):
        self.session_db_object = session_db_object
        self.crawler = crawler
        self.db_fields_pending_saves = set()

    def process_tg_update(self, update: Update) -> None:
        if not isinstance(update, Update):
            raise ValueError(
                f'Unknown update type {type(update)} received instead of Update.',
            )

        try:
            if update.message:
                private_chat_update = PrivateChatMessageReceived.from_tg_update(update)
            elif update.edited_message:
                private_chat_update = PrivateChatMessageEdited.from_tg_update(update)
            elif update.callback_query:
                private_chat_update = PrivateChatCallbackQuery.from_tg_update(update)
            else:
                raise PrivateChatStateMachine.IrrelevantTgUpdate(
                    'Can`t process update of unknown type.',
                )
        except ValidationError as error:
            raise PrivateChatStateMachine.IrrelevantTgUpdate('Bad update object.') from error

        self._update_last_update_db_fields_lazy(private_chat_update)
        self._update_interacted_at_db_field_lazy()
        self.crawler.process(private_chat_update)
        self._update_state_machine_locator_db_field_lazy(self.crawler.current_state.locator)

    def _update_last_update_db_fields_lazy(self, private_chat_update: Any) -> None:
        match private_chat_update:
            case PrivateChatMessageReceived():
                self._update_last_update_tg_username_db_field_lazy(private_chat_update.from_.username)
                self._update_last_update_language_code_field_lazy(private_chat_update.from_.language_code)
            case PrivateChatMessageEdited():
                self._update_last_update_tg_username_db_field_lazy(private_chat_update.from_.username)
                self._update_last_update_language_code_field_lazy(private_chat_update.from_.language_code)
            case PrivateChatCallbackQuery():
                self._update_last_update_tg_username_db_field_lazy(private_chat_update.from_.username)
                self._update_last_update_language_code_field_lazy(private_chat_update.from_.language_code)

    @validate_arguments
    def switch_to(self, locator: Locator) -> None:
        self.crawler.switch_to(locator)
        self._update_state_machine_locator_db_field_lazy(self.crawler.current_state.locator)

    def _update_last_update_tg_username_db_field_lazy(self, tg_username: str | None) -> None:
        tg_username_str = tg_username or ''

        if self.session_db_object.last_update_tg_username == tg_username_str:
            return

        self.session_db_object.last_update_tg_username = tg_username_str
        self.db_fields_pending_saves.add('last_update_tg_username')

    def _update_last_update_language_code_field_lazy(self, language_code: str | None) -> None:
        language_code = language_code or ''

        if self.session_db_object.last_update_language_code == language_code:
            return

        self.session_db_object.last_update_language_code = language_code
        self.db_fields_pending_saves.add('last_update_language_code')

    def _update_interacted_at_db_field_lazy(self) -> None:
        self.session_db_object.interacted_at = timezone.now()
        self.db_fields_pending_saves.add('interacted_at')

    def _update_state_machine_locator_db_field_lazy(self, locator: Locator | None) -> None:
        if locator:
            if self.session_db_object.state_machine_locator != locator:
                self.session_db_object.state_machine_locator = locator
                self.db_fields_pending_saves.add('state_machine_locator')
        else:
            if self.session_db_object.state_machine_locator:
                self.session_db_object.state_machine_locator = None
                self.db_fields_pending_saves.add('state_machine_locator')

    def save_lazy_updates_to_db(self) -> None:
        if not self.db_fields_pending_saves:
            return

        self.session_db_object.save(update_fields=self.db_fields_pending_saves)
        self.db_fields_pending_saves.clear()


@final
class PrivateChatStateMachine:
    router: Router
    session_model: Type[AbstractPrivateChatSessionModel]
    context_funcs: tuple[PrivateChatContextFunc]
    DEFAULT_CONTEXT_FUNCS = (
        partial(SyncTgClient.setup, token=settings.ENV.TG.BOT_TOKEN),
    )

    class NotFoundSessionError(RuntimeError):
        pass

    class IrrelevantTgUpdate(ValueError):
        pass

    @validate_arguments
    def __init__(
        self,
        *,
        router: Router,
        session_model: Type[AbstractPrivateChatSessionModel],
        context_funcs: Sequence[PrivateChatContextFunc] | None = DEFAULT_CONTEXT_FUNCS,
    ):
        self.router = router
        self.context_funcs = tuple(context_funcs) or tuple()
        self.session_model = session_model

    @contextmanager
    def restore_or_create_session_from_tg_update(
        self,
        update: Update,
        *,
        atomic: bool = True,
    ):
        """Restore old session from DB or create new one from Telegram Update.

        Raise ValueError if update object can not be processed by PrivateChatStateMachine.
        """
        tg_chat_id, tg_user_id = self._find_session_ids_in_tg_update(update)

        with ExitStack() as stack:
            session_queryset = self.session_model.objects.all()

            if atomic:
                stack.enter_context(transaction.atomic())
                session_queryset = self.session_model.objects.select_for_update()

            session_db_object, _ = session_queryset.get_or_create(tg_chat_id=tg_chat_id, defaults={
                'tg_user_id': tg_user_id,
            })

            crawler = Crawler(router=self.router)
            session = ActivePrivateChatSession(
                session_db_object=session_db_object,
                crawler=crawler,
            )

            self._restore_session_crawler_state_if_possible(session)
            self._enter_common_session_contexts(stack, session)

            yield session

            session.save_lazy_updates_to_db()

    @contextmanager
    def restore_session(
        self,
        tg_chat_id: int,
        *,
        atomic: bool = True,
    ):
        """Restore old session from DB.

        Raise NotFoundSessionError if session specified not exist. Crawler will stay unassigned if session locator
        is empty or restore failed.
        """
        with ExitStack() as stack:
            session_queryset = self.session_model.objects.all()

            if atomic:
                stack.enter_context(transaction.atomic())
                session_queryset = self.session_model.objects.select_for_update()

            try:
                session_db_object = session_queryset.get(tg_chat_id=tg_chat_id)
            except self.session_model.DoesNotExist:
                raise self.NotFoundSessionError(
                    f'Not found session with tg_chat_id={tg_chat_id}.',
                )

            crawler = Crawler(router=self.router)
            session = ActivePrivateChatSession(
                session_db_object=session_db_object,
                crawler=crawler,
            )

            self._restore_session_crawler_state_if_possible(session)
            self._enter_common_session_contexts(stack, session)

            yield session

            session.save_lazy_updates_to_db()

    def _restore_session_crawler_state_if_possible(self, session: ActivePrivateChatSession) -> None:
        try:
            restored_locator = session.session_db_object.state_machine_locator
            session.crawler.restore(restored_locator)
        except ValidationError:
            session._update_state_machine_locator_db_field_lazy(None)
            logger.warning(
                'Reset invalid state locator of session tg_chat_id=%s',
                session.session_db_object.tg_chat_id,
            )
        except LocatorError:
            session._update_state_machine_locator_db_field_lazy(None)
            logger.warning(
                'Reset not found state locator of session tg_chat_id=%s',
                session.session_db_object.tg_chat_id,
            )

    def _enter_common_session_contexts(self, exit_stack: ExitStack, session: ActivePrivateChatSession) -> None:
        exit_stack.enter_context(session.session_db_object.set_as_current())

        for context_func in self.context_funcs:
            exit_stack.enter_context(context_func())

    def _find_session_ids_in_tg_update(self, update: Update) -> tuple[int, int]:  # noqa C901 CCR001
        """Return ids or raise IrrelevantTgUpdate if lookup failed."""
        if update.message:
            if update.message.chat.type != 'private':
                raise self.IrrelevantTgUpdate(
                    f'Got update with message for non private chat {update.message.chat.type}.',
                )

            if not update.message.from_:
                raise self.IrrelevantTgUpdate(
                    'Got update with message without author specified.',
                )

            return update.message.chat.id, update.message.from_.id

        if update.edited_message:
            if update.edited_message.chat.type != 'private':
                raise self.IrrelevantTgUpdate(
                    f'Got update with edited message for non private chat {update.edited_message.chat.type}.',
                )

            if not update.edited_message.from_:
                raise self.IrrelevantTgUpdate(
                    'Got update with edited message without author specified.',
                )

            return update.edited_message.chat.id, update.edited_message.from_.id

        if update.callback_query:
            if not update.callback_query.message:
                raise self.IrrelevantTgUpdate(
                    'Got update with callback query without message specified.',
                )

            if update.callback_query.message.chat.type != 'private':
                raise self.IrrelevantTgUpdate(
                    f'Got update with callback query for non private chat {update.callback_query.message.chat.type}.',
                )

            if not update.callback_query.from_:
                raise self.IrrelevantTgUpdate(
                    'Got update with callback query without author specified.',
                )

            return update.callback_query.message.chat.id, update.callback_query.from_.id

        raise self.IrrelevantTgUpdate('Can`t find session ids in update of unknown type.')
