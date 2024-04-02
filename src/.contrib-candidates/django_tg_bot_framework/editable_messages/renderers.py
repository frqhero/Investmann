from itertools import groupby
from typing import Union, Callable, TYPE_CHECKING

import tg_api

from mysent import (
    render_chevron_template,
    BaseRenderer,
    Message,
)
from .exceptions import EditableMessagesRenderError

if TYPE_CHECKING:
    from .models import (
        TgTextMessage,
        TgImageMessage,
        TgDocumentMessage,
        TgInlineButton,
    )

MessageRequest = Union[
    tg_api.SendMessageRequest,
    tg_api.SendBytesPhotoRequest,
    tg_api.SendUrlPhotoRequest,
    tg_api.SendUrlDocumentRequest,
    tg_api.SendBytesDocumentRequest,
]
MessageResponse = Union[
    tg_api.SendMessageResponse,
    tg_api.SendPhotoResponse,
    tg_api.SendDocumentResponse,
]
TgMessage = Union[
    'TgTextMessage',
    'TgImageMessage',
    'TgDocumentMessage',
]
MessageOrderNumber = int
ChatIdGetterType = Callable[[], int]  # TODO Уточнить возможные типы для chat_id
LanguageGetterType = Callable[[], str]


class MessageSeriesRequests(list[MessageRequest]):

    def send(self, raise_if_empty: bool = False) -> list[MessageResponse]:
        if raise_if_empty and not self:
            raise EditableMessagesRenderError('Message sending request is empty')
        responses = []
        for message in self:
            responses.append(message.send())
        return responses


class EditableMessagesBaseRenderer(BaseRenderer):
    def __init__(
        self,
        chat_id_getter: ChatIdGetterType,
        language_getter: LanguageGetterType,
        *,
        empty_value=None,
        use_placeholder: bool = True,
        template_engine: Callable = render_chevron_template,
    ):
        self.get_chat_id = chat_id_getter
        self.get_language = language_getter
        super().__init__(
            use_placeholder=use_placeholder,
            template_engine=template_engine,
            empty_value=MessageSeriesRequests() if empty_value is None else empty_value,
        )

    def __call__(self, message_contract: Message, context: dict) -> MessageSeriesRequests:
        if (
            message_contract.languages is not None
            and self.get_language() not in message_contract.languages
        ):
            return self.empty_value
        return super().__call__(message_contract, context)


class RenderPlaceholderMixin:
    def render_placeholder(self: EditableMessagesBaseRenderer, message_contract: Message, context: dict):
        sending_requests = MessageSeriesRequests()
        language = self.get_language()
        buttons = [
            tg_api.InlineKeyboardButton(
                text=button.sense,
                callback_data=button.action,
            )
            for button in message_contract.get_buttons(language)
        ]
        message_request = tg_api.SendMessageRequest(
            text=self.process_templating(message_contract.placeholder, context) or '<empty>',
            chat_id=self.get_chat_id(),
            reply_markup=tg_api.InlineKeyboardMarkup(inline_keyboard=[buttons]),
        )
        sending_requests.append(message_request)
        return sending_requests


class MockTgRenderer(RenderPlaceholderMixin, EditableMessagesBaseRenderer):
    pass


class DbTgRenderer(RenderPlaceholderMixin, EditableMessagesBaseRenderer):
    def render_message(self, message_contract: Message, context: dict):
        sending_requests = MessageSeriesRequests()
        messages = self.get_messages(message_contract)
        keyboards = self.get_keyboards(message_contract)
        for message in messages:
            if keyboard := keyboards.get(message.message_order):
                message._keyboard = keyboard
            sending_requests.append(
                self.render_to_tg_request(message, context),
            )

        return sending_requests

    def get_messages(self, message_contract: Message) -> list[TgMessage]:
        from .models import TgMessageSeries

        required_messages = []
        for model in TgMessageSeries.message_models:
            messages = model.objects.filter(
                series__draft=False,
                series__namespace=message_contract.namespace,
                series__name=message_contract.name,
                series__language_code=self.get_language(),
            )
            required_messages.extend(list(messages))
        required_messages.sort(key=lambda msg: msg.message_order)
        return required_messages

    def get_keyboards(
        self,
        message_contract: Message,
    ) -> dict[MessageOrderNumber, list[list['TgInlineButton']]]:
        """Return dict with keyboard grouped by message number in series.

        {
            1: [[TgInlineButton, TgInlineButton], [TgInlineButton, TgInlineButton]],
            2: [[TgInlineButton, TgInlineButton], [TgInlineButton, TgInlineButton]],
            ...
        }
        """
        from .models import TgInlineButton

        language = self.get_language()
        buttons = TgInlineButton.objects.filter(
            series__draft=False,
            series__namespace=message_contract.namespace,
            series__name=message_contract.name,
            series__language_code=language,
        ).order_by('message_number', 'row', 'position_in_row')

        buttons_grouped_by_messages = groupby(buttons, key=lambda btn: btn.message_number)
        keyboards = {}
        for message_number, buttons_for_message in buttons_grouped_by_messages:
            keyboards[message_number] = [
                list(row)
                for _, row in groupby(buttons_for_message, key=lambda btn: btn.row)
            ]
        return keyboards

    def render_to_tg_request(self, message: TgMessage, context: dict) -> MessageRequest:
        from .models import TgTextMessage, TgImageMessage, TgDocumentMessage

        tg_request = None
        match message:
            case TgTextMessage():
                text = self.process_templating(message.text, context) or '<empty>'
                tg_request = tg_api.SendMessageRequest(
                    text=text,
                    chat_id=self.get_chat_id(),
                    disable_web_page_preview=message.disable_web_page_preview,
                    parse_mode=message.parse_mode or None,
                    protect_content=message.protect_content,
                    disable_notification=message.series.disable_notification,
                )
            case TgImageMessage():
                tg_request = tg_api.SendBytesPhotoRequest(
                    photo=message.image.read(),
                    chat_id=self.get_chat_id(),
                    has_spoiler=message.has_spoiler,
                    disable_notification=message.series.disable_notification,
                )
            case TgDocumentMessage():
                tg_request = tg_api.SendBytesDocumentRequest(
                    document=message.file.read(),
                    filename=message.file.name,
                    chat_id=self.get_chat_id(),
                    disable_content_type_detection=message.disable_content_type_detection,
                    disable_notification=message.series.disable_notification,
                )

        if tg_request is None:
            raise EditableMessagesRenderError(f'Unknown type of message: {message.__class__}')

        if keyboard := getattr(message, '_keyboard', None):
            inline_keyboard = [
                self.get_row_of_inline_buttons(row, context)
                for row in keyboard
                if row
            ]
            tg_request.reply_markup = tg_api.InlineKeyboardMarkup(
                inline_keyboard=inline_keyboard or None,
            )
        return tg_request

    def get_row_of_inline_buttons(
        self,
        row: list['TgInlineButton'],
        context: dict,
    ) -> list[tg_api.InlineKeyboardButton]:
        row_of_inline_buttons = []
        for button in row:
            text = self.process_templating(button.text, context) or '<empty>'
            inline_button = tg_api.InlineKeyboardButton(
                text=text,
                callback_data=button.callback_data,
                url=button.url,
            )
            row_of_inline_buttons.append(inline_button)
        return row_of_inline_buttons
