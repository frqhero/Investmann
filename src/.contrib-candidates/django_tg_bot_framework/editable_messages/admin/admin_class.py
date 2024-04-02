from enum import Enum
from typing import NamedTuple

from django.contrib import admin
from django.urls import path

from mysent import MessageRouter, MessageLocator
from pydantic import ValidationError as PydanticValidationError
from django.contrib.admin.options import csrf_protect_m
from django.core.handlers.wsgi import WSGIRequest
from django.template.response import TemplateResponse
from django.utils.safestring import mark_safe

from .actions import delete_selected_messages, save_messages, make_active
from .filters import TgEditableMessagesStatusFilter, TgEditableMessagesLanguageFilter
from .inlines import ImageMessageInline, DocumentMessageInline, TextMessageInline
from .save_load_messages import upload_messages
from ..db_checker import DbStatement
from ..models import TgMessageSeries

LanguageCode = str
Verbose = str


class MissedMessage(NamedTuple):
    sense: str
    namespace: str
    name: str
    language: str
    draft: int | None


class EditableMessagesAdmin(admin.ModelAdmin):
    message_router: MessageRouter = None
    languages: dict[LanguageCode, Verbose] = {}

    class MessageStatus(Enum):
        GOOD = '🟢 OK'
        REDUNDANT = '🔵 Лишнее'
        DRAFT = '🟡 Черновик'
        BAD = '🔴 Проблемное'

    fieldsets = [
        (
            None,
            {
                "fields": [
                    "namespace",
                    "name",
                    "language_code",
                    "draft",
                ],
            },
        ),
        (
            "Содержимое",
            {
                "fields": ["disable_notification", "show_attributes", "show_buttons"],
            },
        ),
    ]
    list_display = [
        "show_sense",
        "show_message_locator",
        "get_language_code",
        "show_status",
    ]
    list_display_links = [
        "show_sense",
        "show_message_locator",
    ]
    list_filter = [
        TgEditableMessagesLanguageFilter,
        TgEditableMessagesStatusFilter,
    ]
    readonly_fields = [
        "show_attributes",
        "show_sense",
        "show_status",
        "show_buttons",
        "get_language_code",
    ]
    ordering = ["namespace", "name", "language_code"]

    actions = [
        delete_selected_messages,
        save_messages,
        make_active,
    ]

    inlines = [
        TextMessageInline,
        ImageMessageInline,
        DocumentMessageInline,
    ]

    class Media:
        css = {
            'all': [
                'admin/sticky-save.css',
            ],
        }
        js = [
            'admin/save-hotkey.js',
        ]

    def __init__(self, model, admin_site):
        self.db_statement = DbStatement(self.message_router, self.languages.keys())
        super().__init__(model, admin_site)

    def get_form(self, request, obj=None, change=False, **kwargs):
        self.model.language_code.field.choices = self.languages.items()
        self.model.language_code.field.default = list(self.languages.items())[0]
        return super().get_form(request, obj, change, **kwargs)

    def get_readonly_fields(
        self,
        request: WSGIRequest,
        obj: TgMessageSeries | None = None,
    ) -> list[str]:
        user = request.user
        if not obj or user.is_superuser or user.has_perm(
            "editable_messages.can_change_ready_messages",
        ):
            return self.readonly_fields
        if obj in self.db_statement.active:
            return self.readonly_fields + [
                "namespace",
                "name",
                "language_code",
                "draft",
            ]
        return self.readonly_fields

    def has_delete_permission(
        self,
        request: WSGIRequest,
        obj: TgMessageSeries | None = None,
    ) -> bool:
        user = request.user
        if not obj or user.is_superuser or user.has_perm(
            "editable_messages.can_change_ready_messages",
        ):
            return True
        return obj not in self.db_statement.active

    @admin.display(description="Используемые параметры")
    def show_attributes(self, obj: TgMessageSeries) -> str | None:
        if context_scheme := self.message_router.get_context_scheme(obj.message_locator):
            return '\n'.join([
                '{{ %s }} - %s' % (param_name, param_description)
                for param_name, param_description
                in context_scheme.items()
            ])
        return "в сообщении нет параметров"

    @admin.display(description="Язык")
    def get_language_code(self, obj: TgMessageSeries) -> str:
        return self.languages.get(obj.language_code, obj.language_code)

    @admin.display(description="Локатор")
    def show_message_locator(self, obj: TgMessageSeries) -> str:
        return str(obj)

    @admin.display(description="Требуемые кнопки")
    def show_buttons(self, obj: TgMessageSeries):
        if buttons := self.message_router.get_buttons_scheme(obj.message_locator, language=obj.language_code):
            missed_callbacks = self.db_statement.missed_buttons.get_for_series(obj)
            styles = (
                '',  # good style
                'color: #ff001c;font-weight: normal;',  # bad style
            )
            buttons_div = [
                '<span style="{}">[ {} ] - {}</span>'.format(
                    styles[button.action in missed_callbacks],
                    button.action,
                    button.sense,
                )
                for button in buttons
            ]

            return mark_safe('</br>'.join(buttons_div))
        return "нет обязательных кнопок"

    @admin.display(description="Суть", empty_value="—")
    def show_sense(self, obj: TgMessageSeries) -> str | None:
        return self.message_router.get_sense(obj.message_locator)

    def get_status(self, obj: TgMessageSeries) -> MessageStatus:
        if obj.draft:
            return self.MessageStatus.DRAFT
        if obj in self.db_statement.active:
            if obj in self.db_statement.bad:
                return self.MessageStatus.BAD
            if obj in self.db_statement.good:
                return self.MessageStatus.GOOD
        return self.MessageStatus.REDUNDANT

    def get_trouble_text(self, obj: TgMessageSeries) -> str:
        troubles = []
        if obj in self.db_statement.empty:
            troubles.append('Отсутствует контент')
        if obj in self.db_statement.missed_buttons:
            troubles.append('Не хватает кнопок')
        return ', '.join(troubles)

    @admin.display(description="Статус")
    def show_status(self, obj: TgMessageSeries) -> str:
        status = self.get_status(obj)
        status_text = status.value
        if status == self.MessageStatus.DRAFT:
            title = 'title="Помечено как черновик. Не используется в работе бота"'
        elif status == self.MessageStatus.BAD:
            status_text = '🔴 ' + self.get_trouble_text(obj)
            title = 'title="Нарушает работу бота"'
        elif status == self.MessageStatus.GOOD:
            title = 'title="Прошло проверку и исправно работает"'
        else:
            title = 'title="Не используется в работе бота"'

        style = 'style="white-space:nowrap;"'
        return mark_safe(f'<span {style} {title}>{status_text}</span>')

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        self.db_statement = DbStatement(self.message_router, self.languages.keys())
        extra_context = {
            'troubles': self._get_messages_troubles(),
        }
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self.db_statement = DbStatement(self.message_router, self.languages.keys())
        return super().change_view(request, object_id, form_url, extra_context)

    def _get_messages_troubles(self):
        missed = [
            MissedMessage(
                sense=self.message_router[locator].sense,
                namespace=locator.namespace,
                name=locator.name,
                language=self.languages.get(language, language),
                draft=self._check_for_draft(language, locator),
            )
            for language, locators in self.db_statement.missed.items()
            for locator in locators
        ]
        return {
            'bad_messages': bool(self.db_statement.bad),
            'missed': missed,
        }

    def _check_for_draft(self, language: str, locator: MessageLocator) -> int | None:
        series = next(filter(
            lambda s: s.name == locator.name and s.namespace == locator.namespace and s.language_code == language,
            self.db_statement.all_series,
        ), None)
        if series and series.draft:
            return series.pk

    def get_inlines(self, request, obj: TgMessageSeries):
        inlines = super().get_inlines(request, obj)
        message_number_choices = {
            (message.message_order, message.message_order)
            for message in self.db_statement.all_messages
            if message.series == obj
        }
        buttons_inline = []
        for model in self.model.button_models:
            model.message_number.field.choices = message_number_choices
            buttons_inline.append(
                type(
                    f'{model.__name__}Inline',
                    (admin.TabularInline,),
                    {'extra': 0, 'model': model},
                ),
            )
        return inlines + buttons_inline

    def _is_alarm_needed(
        self,
        request: WSGIRequest,
        series: TgMessageSeries,
    ) -> bool:
        user_has_delete_permission = self.has_delete_permission(
            request, series,
        )
        if user_has_delete_permission:
            return series in self.db_statement.active
        return False

    def get_actions(self, request: WSGIRequest) -> dict:
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def get_urls(self):
        urls = super(EditableMessagesAdmin, self).get_urls()
        custom_urls = [
            path(
                "load_messages_view/",
                self.load_messages_view,
                name="load_messages_view",
            ),
        ]
        return custom_urls + urls

    def load_messages_view(self, request: WSGIRequest):
        if request.method == 'POST' and "fileInput" in request.FILES:
            return self.render_imported_messages_view(request)

        context = {
            **self.admin_site.each_context(request),
        }
        return TemplateResponse(
            request,
            "admin/editable_messages/tgmessageseries/load_msgs.html",
            context,
        )

    def render_imported_messages_view(self, request: WSGIRequest):
        replace_existing_msgs = bool(
            request.POST.get("replaceExistingMsgs", False),
        )
        context = {
            **self.admin_site.each_context(request),
        }
        try:
            context.update(upload_messages(
                request.FILES["fileInput"].file,
                replace_existing_msgs,
            ))
        except PydanticValidationError as error:
            context.update({
                "summary": "Обнаружены ошибки:",
                "errors": error.errors(),
            })
        except KeyError:
            context.update({
                "summary": "Обнаружены ошибки:",
                "errors": 'Неверный формат файла',
            })
        return TemplateResponse(
            request,
            "admin/editable_messages/tgmessageseries/imported_msgs.html",
            context=context,
        )

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None,
    ):
        if obj:
            extra_context = {
                'subtitle': self.show_sense(obj),
                'title': self.show_status(obj),
                'show_alarm': self._is_alarm_needed(request, obj),
            }
            context.update(extra_context)
        return super().render_change_form(
            request,
            context,
            add=add,
            change=change,
            form_url=form_url,
            obj=obj,
        )

    def render_delete_form(
        self,
        request: WSGIRequest,
        context: dict,
    ) -> TemplateResponse:
        series_pk = request.resolver_match.kwargs['object_id']
        series = TgMessageSeries.objects.get(pk=series_pk)
        context["show_alarm"] = self._is_alarm_needed(
            request, series,
        )
        return super().render_delete_form(request, context)
