from typing import final, Literal

from pydantic import Field
from tg_api import tg_types


class PrivateChat(tg_types.Chat):
    """Как обычный Chat из библиотеки Tg API, но с более строгой схемой данных.

    Схема данных создана специально для работы с приватными чатами. На данные накладываются
    более строгие ограничения, чтобы в прикладном коде реже приходилось писать условия
    для проверки полей: пустое значение или нет, верно заполнено или нет. Также, лучше
    работают подсказки в IDE, и меньше ругается линтер.
    """

    # Fields with extra validation for private chats:
    type: Literal['private']  # noqa A003


class PrivateChatMessage(tg_types.Message):
    """Структура данных, похожая на Message из Tg Bot API, но с более строгими ограничениями в схеме данных.

    Схема данных создана специально для работы с приватными чатами. На данные накладываются
    более строгие ограничения, чтобы в прикладном коде реже приходилось писать условия
    для проверки полей: пустое значение или нет, верно заполнено или нет. Также, лучше
    работают подсказки в IDE, и меньше ругается линтер.
    """

    # Fields with extra validation for private chats:
    from_: tg_types.User = Field(alias='from')
    chat: PrivateChat

    # Non relevant attributes for private chats should always be empty:
    message_thread_id: None = None
    sender_chat: None = None
    is_topic_message: None = None
    is_automatic_forward: None = None
    author_signature: None = None
    new_chat_title: None = None
    new_chat_photo: None = None
    delete_chat_photo: None = None
    new_chat_members: None = None
    left_chat_member: None = None
    group_chat_created: None = None
    supergroup_chat_created: None = None
    channel_chat_created: None = None
    migrate_to_chat_id: None = None
    migrate_from_chat_id: None = None
    forum_topic_created: None = None
    forum_topic_edited: None = None
    forum_topic_closed: None = None
    forum_topic_reopened: None = None
    general_forum_topic_hidden: None = None
    general_forum_topic_unhidden: None = None
    video_chat_scheduled: None = None
    video_chat_started: None = None
    video_chat_ended: None = None
    video_chat_participants_invited: None = None
    web_app_data: None = None


@final
class PrivateChatMessageReceived(PrivateChatMessage):
    update_id: int = Field(description='Field value is copied from original Tg Update object')

    @classmethod
    def from_tg_update(cls, update):
        payload = update.message.dict(by_alias=True) | {'update_id': update.update_id}
        return cls.parse_obj(payload)


@final
class PrivateChatMessageEdited(PrivateChatMessage):
    update_id: int = Field(description='Field value is copied from original Tg Update object')

    @classmethod
    def from_tg_update(cls, update):
        payload = update.edited_message.dict(by_alias=True) | {'update_id': update.update_id}
        return cls.parse_obj(payload)


@final
class PrivateChatCallbackQuery(tg_types.CallbackQuery):
    update_id: int = Field(description='Field value is copied from original Tg Update object')

    # Fields with extra validation for private chats:
    from_: tg_types.User = Field(alias='from')
    message: PrivateChatMessage = Field(description='Message with the callback button that originated the query.')

    data: str = Field(description='Data associated with the callback button. Be aware that the message '
                                  'originated the query can contain no callback buttons with this data.')

    @classmethod
    def from_tg_update(cls, update):
        payload = update.callback_query.dict(by_alias=True) | {'update_id': update.update_id}
        return cls.parse_obj(payload)
