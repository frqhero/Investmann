from django.conf import settings

from django_tg_bot_framework.editable_messages import (
    DbTgRenderer,
    EditableMessagesRouter,
)
from django_tg_bot_framework.private_chats import (
    PrivateChatState,
    PrivateChatStateMachine,
    PrivateChatMessageReceived,
    PrivateChatCallbackQuery,
)
from django_tg_bot_framework.funnels import AbstractFunnelEvent
from mysent import Message, Button
from yostate import Router, Locator


from trigger_mailing import funnels as trigger_funnels
from trigger_mailing.state_machine import (
    state_machine as trigger_funnel_state_machine,
    FIRST_MAILING_FUNNEL_SLUG,
    SECOND_MAILING_FUNNEL_SLUG,
)

from .models import Conversation
from .decorators import redirect_menu_commands

router = Router(decorators=[redirect_menu_commands])
state_machine = PrivateChatStateMachine(
    router=router,
    session_model=Conversation,
    context_funcs=[
        trigger_funnel_state_machine.process_collected,
        lambda: AbstractFunnelEvent.set_default_tg_user_id(
            Conversation.current.tg_user_id,
        ),
        *PrivateChatStateMachine.DEFAULT_CONTEXT_FUNCS,
    ],
)


def language_getter() -> str:
    bot_languages = settings.BOT_LANGUAGES
    conversation: Conversation = Conversation.current
    user_language = conversation.force_language or conversation.last_update_language_code
    if user_language not in bot_languages:
        return 'ru'
    return user_language


renderer = DbTgRenderer(
    chat_id_getter=lambda: Conversation.current.tg_chat_id,
    language_getter=language_getter,
    use_placeholder=True,
)
message_router = EditableMessagesRouter(renderer)


@router.register('/')
class FirstUserMessageState(PrivateChatState):
    """Состояние используется для обработки самого первого сообщения пользователя боту.

    Текст стартового сообщения от пользователя игнорируется, а бот переключается в
    следующий стейт, где уже отправит пользователю приветственное сообщение.

    Если вы хотите перекинуть бота в начало диалога -- на "стартовый экран" -- , то используйте другое
    состояние с приветственным сообщением. Это нужно только для обработки первого сообщения от пользователя.
    """

    def process_message_received(self, message: PrivateChatMessageReceived) -> Locator | None:
        # Ignore any user input, redirect to welcome message
        return Locator('/welcome/')


@router.register('/welcome/')
class WelcomeState(PrivateChatState):
    class EditableMessages:
        welcome = Message(
            'Приветствие',
            placeholder='Wellcome',
        )
        echo = Message(
            'Эхо сообщение',
            placeholder='Message you sent: {{ echo }}',
            context_scheme={'echo': 'Сообщение, присланное пользователем'},
        )

    def enter_state(self) -> Locator | None:
        self.EditableMessages.welcome.render().send()

    def process_message_received(self, message: PrivateChatMessageReceived) -> Locator | None:
        context = {'echo': message.text}
        self.EditableMessages.echo.render(context).send()
        return Locator('/welcome/')


@router.register('/main-menu/')
class MainMenuState(PrivateChatState):
    _editable_messages = {
        'welcome': Message(
            'Главное меню',
            placeholder='Welcome!',
            buttons=[
                Button('Назад в приветствие', action='welcome'),
                Button('Запустить вторую рассылку', action='trigger_second_mailing'),
                Button('Switch to English', action='lang_en', languages={'ru'}),
                Button('Переключиться на русский', action='lang_ru', languages={'en'}),
            ],
        ),
        'second-trigger-mailing': Message(
            'Отправка второй триггерной рассылки',
        ),
        'echo': Message(
            'Эхо сообщение',
            context_scheme={'echo': 'Сообщение, присланное пользователем'},
        ),
    }

    def enter_state(self) -> Locator | None:
        trigger_funnel_state_machine.push_event(trigger_funnels.LeadNavigatedToMainMenu())
        self._editable_messages['welcome'].render().send()

    def process_callback_query(self, callback_query: PrivateChatCallbackQuery) -> Locator | None:
        match callback_query.data:
            case 'welcome':
                return Locator('/welcome/')
            case callback_query.data if callback_query.data.startswith('lang_'):
                new_lang = callback_query.data.removeprefix('lang_')
                current_conversation: Conversation = Conversation.current
                current_conversation.force_language = new_lang
                current_conversation.save()
                return Locator('/language/change/', params={'lang': new_lang})
            case 'trigger_second_mailing':
                trigger_funnel_state_machine.push_event(
                    trigger_funnels.LeadLaunchedSecondMailing(),
                )
                second_trigger_message = self._editable_messages['second-trigger-mailing']
                second_trigger_message.render().send()

    def process_message_received(self, message: PrivateChatMessageReceived) -> Locator | None:
        echo_message = self._editable_messages['echo']
        context = {'echo': message.text}
        echo_message.render(context).send()
        return Locator('/main-menu/')


@router.register('/language/change/')
class LanguageChangeState(PrivateChatState):
    lang: str

    class EditableMessages:
        change_lang = Message(
            'Смена языка',
            placeholder='Switching to {{ lang }}',
            context_scheme={'lang': 'Язык на который переключился пользователь'},
            buttons=[
                Button('Send only English message', action='en', languages={'en'}),
                Button('Прислать сообщение для русского языка', action='ru', languages={'ru'}),
            ],
        )

    def enter_state(self) -> Locator | None:
        context = {'lang': self.lang}
        self.EditableMessages.change_lang.render(context).send()

    def process_callback_query(self, callback_query: PrivateChatCallbackQuery) -> Locator | None:
        return Locator('/language/message/', params={'lang': callback_query.data})


@router.register('/language/message/')
class LanguageMessageState(PrivateChatState):
    lang: str

    class EditableMessages:
        only_ru = Message(
            'Сообщение только на русском',
            placeholder='Это сообщение приходит только на русском языке',
            languages={'ru'},
        )
        only_en = Message(
            'Only English message',
            placeholder='This message sent only for English',
            languages={'en'},
        )

    def enter_state(self) -> Locator | None:
        if self.lang == 'ru':
            self.EditableMessages.only_ru.render().send()
        elif self.lang == 'en':
            self.EditableMessages.only_en.render().send()
        return Locator('/main-menu/')


@router.register('/first-trigger-mailing/')
class FirstTriggerMailingState(PrivateChatState):
    class EditableMessages:
        mailing = Message(
            'Сообщение для первой рассылки',
            buttons=[
                Button('Выбор первого варианта', action='buy_first'),
                Button('Выбор второго варианта', action='buy_second'),
                Button('Выбор третьего варианта', action='buy_third'),
            ],
        )
        choice = Message(
            'Выбор пользователя',
            context_scheme={'choice': 'выбранный пункт меню'},
        )

    def enter_state(self) -> Locator | None:
        self.EditableMessages.mailing.render().send()
        trigger_funnel_state_machine.push_event(trigger_funnels.MailingWasSentToLead(
            funnel_slug=FIRST_MAILING_FUNNEL_SLUG,
        ))

    def process_callback_query(self, callback_query: PrivateChatCallbackQuery) -> Locator | None:
        choice_message = self.EditableMessages.choice
        contex = {'choice': callback_query.data}
        choice_message.render(contex).send()

        match callback_query.data:
            case 'buy_first' | 'buy_second':
                trigger_funnel_state_machine.push_event(
                    trigger_funnels.MailingTargetActionAcceptedByLead(
                        action=callback_query.data,
                        funnel_slug=FIRST_MAILING_FUNNEL_SLUG,
                    ),
                )
            case 'stop_mailing':
                trigger_funnel_state_machine.push_event(trigger_funnels.LeadUnsubscribed(
                    funnel_slug=FIRST_MAILING_FUNNEL_SLUG,
                ))


@router.register('/second-trigger-mailing/')
class SecondTriggerMailingState(PrivateChatState):
    class EditableMessages:
        mailing = Message('Сообщение для второй рассылки')

    def enter_state(self) -> Locator | None:
        self.EditableMessages.mailing.render().send()

        trigger_funnel_state_machine.push_event(trigger_funnels.MailingWasSentToLead(
            funnel_slug=SECOND_MAILING_FUNNEL_SLUG,
        ))


message_router.fill_message_router_from_states(router)
