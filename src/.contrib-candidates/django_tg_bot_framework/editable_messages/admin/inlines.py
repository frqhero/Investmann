from django.contrib.admin.options import StackedInline
from django.utils.html import format_html
from django.db import models

from .widgets import MonacoEditorWidget
from ..models import TgImageMessage, TgDocumentMessage, TgTextMessage


def image_preview(obj: TgImageMessage):
    if not obj.image:
        return 'Выберите изображение'
    return format_html('<img src="{url}" style="max-height: 200px;"/>', url=obj.image.url)


class ImageMessageInline(StackedInline):
    model = TgImageMessage
    fields = [
        'message_order',
        image_preview,
        'image',
        'has_spoiler',
        'protect_content',
        'series',
    ]
    readonly_fields = [
        image_preview,
    ]
    extra = 0


class DocumentMessageInline(StackedInline):
    model = TgDocumentMessage
    fields = [
        'message_order',
        'file',
        'disable_content_type_detection',
        'protect_content',
        'series',
    ]
    extra = 0


class TextMessageInline(StackedInline):
    model = TgTextMessage
    formfield_overrides = {
        models.TextField: {'widget': MonacoEditorWidget},
    }
    fields = [
        'message_order',
        'text',
        'parse_mode',
        'disable_web_page_preview',
        'protect_content',
        'series',
    ]
    extra = 0
