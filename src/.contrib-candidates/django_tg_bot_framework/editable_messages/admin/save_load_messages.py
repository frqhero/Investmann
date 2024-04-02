import json
from io import BytesIO
from zipfile import ZipFile, is_zipfile

from django.core import serializers
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import QuerySet
from pydantic import BaseModel, PositiveInt, NonNegativeInt

from ..models import (
    TgMessageSeries,
    TgDocumentMessage,
    TgImageMessage,
    TgTextMessage,
    TgInlineButton,
)


class ImportedTextMessage(BaseModel):
    pk: int
    text: str
    protect_content: bool
    disable_web_page_preview: bool
    parse_mode: str
    series: PositiveInt
    message_order: NonNegativeInt


class ImportedImageMessage(BaseModel):
    pk: int
    image: str
    protect_content: bool
    has_spoiler: bool
    series: PositiveInt
    message_order: NonNegativeInt


class ImportedDocumentMessage(BaseModel):
    pk: int
    file: str
    protect_content: bool
    disable_content_type_detection: bool
    series: PositiveInt
    message_order: NonNegativeInt


class ImportedInlineButton(BaseModel):
    pk: int
    text: str
    callback_data: str
    url: str
    series: PositiveInt
    message_number: int
    row: int
    position_in_row: int


class ImportedMessageSeries(BaseModel):
    pk: int
    namespace: str
    name: str
    language_code: str
    draft: bool
    disable_notification: bool


def upload_messages(bytes_io: BytesIO, replace_existing_msgs: bool) -> dict:
    context = {}
    if not is_zipfile(bytes_io):
        context["summary"] = "Обнаружены ошибки:"
        context["errors"] = "Файл не является валидным zip архивом!"
        return context

    with ZipFile(bytes_io, mode="r") as zip_file:
        imported_msgs_series = get_imported_msgs(
            zip_file, "msgs_series.json", ImportedMessageSeries,
        )
        imported_text_msgs = get_imported_msgs(
            zip_file, "texts_msgs.json", ImportedTextMessage,
        )
        imported_img_msgs = get_imported_msgs(
            zip_file, "images_msgs.json", ImportedImageMessage,
        )
        imported_doc_msgs = get_imported_msgs(
            zip_file, "docs_msgs.json", ImportedDocumentMessage,
        )
        imported_inline_buttons = get_imported_msgs(
            zip_file, "inline_buttons.json", ImportedInlineButton,
        )
        db_series = get_db_series(imported_msgs_series)
        with transaction.atomic():
            if replace_existing_msgs:
                series_pks, existing_series_pks = update_message_series(
                    imported_msgs_series,
                    db_series,
                )
                existing_series = existing_series_pks.values()
                for message_model in TgMessageSeries.message_models:
                    message_model.objects \
                        .filter(series__in=existing_series).delete()
                for button_model in TgMessageSeries.button_models:
                    button_model.objects \
                        .filter(series__in=existing_series).delete()
            else:
                series_pks, existing_series_pks = create_message_series(
                    imported_msgs_series,
                    db_series,
                )

            create_text_messages(
                imported_text_msgs,
                series_pks,
                existing_series_pks,
                replace_existing_msgs,
            )
            create_image_messages(
                imported_img_msgs,
                series_pks,
                existing_series_pks,
                replace_existing_msgs,
                zip_file,
            )
            create_document_messages(
                imported_doc_msgs,
                series_pks,
                existing_series_pks,
                replace_existing_msgs,
                zip_file,
            )
            create_inline_buttons(
                imported_inline_buttons,
                series_pks,
                existing_series_pks,
                replace_existing_msgs,
            )

    context["summary"] = "Сообщения успешно загружены!"
    context["upload_log"] = get_upload_messages_log(
        series_pks,
        existing_series_pks,
        replace_existing_msgs,
    )
    return context


def get_imported_msgs(
    zip_file: ZipFile,
    file_name: str,
    imported_model_class: type[BaseModel],
) -> list[BaseModel]:
    imported_msgs = []
    serialized_msgs = zip_file.read(file_name).decode()
    deserialized_msgs = json.loads(serialized_msgs)
    for deserialized_msg in deserialized_msgs:
        fields = deserialized_msg["fields"]
        fields["pk"] = deserialized_msg["pk"]
        imported_msg = imported_model_class(**fields)
        imported_msgs.append(imported_msg)
    return imported_msgs


def get_db_series(
    imported_msgs_series: list[ImportedMessageSeries],
) -> dict[tuple[str, str, str], TgMessageSeries]:
    namespaces = set()
    names = set()
    language_codes = set()
    db_series = {}
    for series in imported_msgs_series:
        namespaces.add(series.namespace)
        names.add(series.name)
        language_codes.add(series.language_code)

    queryset = TgMessageSeries.objects.filter(
        namespace__in=namespaces,
        name__in=names,
        language_code__in=language_codes,
    )
    for series in queryset:
        key = (series.namespace, series.name, series.language_code)
        db_series[key] = series

    return db_series


def create_message_series(
    imported_msgs_series: list[ImportedMessageSeries],
    db_series: dict[tuple[str, str, str], TgMessageSeries],
) -> tuple[dict[int, TgMessageSeries], dict[int, TgMessageSeries]]:
    series_pks = {}
    existing_series_pks = {}
    series_to_create = []
    for imported_msg_series in imported_msgs_series:
        key = (
            imported_msg_series.namespace,
            imported_msg_series.name,
            imported_msg_series.language_code,
        )
        series = db_series.get(key)
        if series:
            existing_series_pks[imported_msg_series.pk] = series
            series_pks[imported_msg_series.pk] = series
            continue
        series = TgMessageSeries(
            namespace=imported_msg_series.namespace,
            name=imported_msg_series.name,
            language_code=imported_msg_series.language_code,
            draft=imported_msg_series.draft,
            disable_notification=imported_msg_series.disable_notification,
        )
        series_pks[imported_msg_series.pk] = series
        series_to_create.append(series)

    if series_to_create:
        TgMessageSeries.objects.bulk_create(
            series_to_create, batch_size=100,
        )

    return series_pks, existing_series_pks


def update_message_series(
    imported_msgs_series: list[ImportedMessageSeries],
    db_series: dict[tuple[str, str, str], TgMessageSeries],
) -> tuple[dict[int, TgMessageSeries], dict[int, TgMessageSeries]]:
    series_pks = {}
    existing_series_pks = {}
    series_to_update = []
    series_to_create = []
    for imported_msg_series in imported_msgs_series:
        create = False
        key = (
            imported_msg_series.namespace,
            imported_msg_series.name,
            imported_msg_series.language_code,
        )
        series = db_series.get(key)
        if not series:
            create = True
            series = TgMessageSeries(
                namespace=imported_msg_series.namespace,
                name=imported_msg_series.name,
                language_code=imported_msg_series.language_code,
            )
        series.draft = imported_msg_series.draft
        series.disable_notification = imported_msg_series.disable_notification

        if create:
            series_to_create.append(series)
        else:
            series_to_update.append(series)
            existing_series_pks[imported_msg_series.pk] = series

        series_pks[imported_msg_series.pk] = series
    bulk_record_message_series(series_to_create, series_to_update)

    return series_pks, existing_series_pks


def bulk_record_message_series(
    series_to_create: list[TgMessageSeries],
    series_to_update: list[TgMessageSeries],
) -> None:
    if series_to_create:
        TgMessageSeries.objects.bulk_create(
            series_to_create,
            batch_size=100,
        )
    if series_to_update:
        TgMessageSeries.objects.bulk_update(
            series_to_update,
            fields=["draft", "disable_notification"],
        )


def create_text_messages(
    imported_text_msgs: list[ImportedTextMessage],
    series_pks: dict[int, TgMessageSeries],
    existing_series_pks: dict[int, TgMessageSeries],
    replace_existing_msgs: bool,
) -> None:
    msgs_to_create = []
    for imported_text_msg in imported_text_msgs:
        if not replace_existing_msgs and imported_text_msg.series in existing_series_pks:
            continue
        msg = TgTextMessage(
            text=imported_text_msg.text,
            protect_content=imported_text_msg.protect_content,
            disable_web_page_preview=imported_text_msg.
            disable_web_page_preview,
            parse_mode=imported_text_msg.parse_mode,
            series=series_pks[imported_text_msg.series],
            message_order=imported_text_msg.message_order,
        )
        msgs_to_create.append(msg)
    if not msgs_to_create:
        return
    TgTextMessage.objects.bulk_create(msgs_to_create, batch_size=100)


def create_image_messages(
    imported_img_msgs: list[ImportedImageMessage],
    series_pks: dict[int, TgMessageSeries],
    existing_series_pks: dict[int, TgMessageSeries],
    replace_existing_msgs: bool,
    zip_file: ZipFile,
) -> None:
    msgs_to_create = []
    for imported_img_msg in imported_img_msgs:
        if not replace_existing_msgs and imported_img_msg.series in existing_series_pks:
            continue
        image_name = imported_img_msg.image
        image = zip_file.read(image_name)
        msg = TgImageMessage(
            image=ContentFile(content=image, name=image_name),
            protect_content=imported_img_msg.protect_content,
            has_spoiler=imported_img_msg.has_spoiler,
            series=series_pks[imported_img_msg.series],
            message_order=imported_img_msg.message_order,
        )
        msgs_to_create.append(msg)
    if not msgs_to_create:
        return
    TgImageMessage.objects.bulk_create(msgs_to_create, batch_size=100)


def create_document_messages(
    imported_doc_msgs: list[ImportedDocumentMessage],
    series_pks: dict[int, TgMessageSeries],
    existing_series_pks: dict[int, TgMessageSeries],
    replace_existing_msgs: bool,
    zip_file: ZipFile,
) -> None:
    msgs_to_create = []
    for imported_doc_msg in imported_doc_msgs:
        if not replace_existing_msgs and imported_doc_msg.series in existing_series_pks:
            continue
        file_name = imported_doc_msg.file
        file = zip_file.read(file_name)
        msg = TgDocumentMessage(
            file=ContentFile(content=file, name=file_name),
            protect_content=imported_doc_msg.protect_content,
            disable_content_type_detection=imported_doc_msg.
            disable_content_type_detection,
            series=series_pks[imported_doc_msg.series],
            message_order=imported_doc_msg.message_order,
        )
        msgs_to_create.append(msg)
    if not msgs_to_create:
        return
    TgDocumentMessage.objects.bulk_create(msgs_to_create, batch_size=100)


def create_inline_buttons(
    imported_inline_buttons: list[ImportedInlineButton],
    series_pks: dict[int, TgMessageSeries],
    existing_series_pks: dict[int, TgMessageSeries],
    replace_existing_msgs: bool,
) -> None:
    buttons_to_create = []
    for imported_inline_button in imported_inline_buttons:
        if not replace_existing_msgs and imported_inline_button.series in existing_series_pks:
            continue
        button = TgInlineButton(
            text=imported_inline_button.text,
            callback_data=imported_inline_button.callback_data,
            url=imported_inline_button.url,
            series=series_pks[imported_inline_button.series],
            message_number=imported_inline_button.message_number,
            row=imported_inline_button.row,
            position_in_row=imported_inline_button.position_in_row,
        )
        buttons_to_create.append(button)
    if not buttons_to_create:
        return
    TgInlineButton.objects.bulk_create(buttons_to_create, batch_size=100)


def get_upload_messages_log(
    series_pks: dict[int, TgMessageSeries],
    existing_series_pks: dict[int, TgMessageSeries],
    replace_existing_msgs: bool,
) -> list[dict[str, str]]:
    upload_log = []
    for pk, series in series_pks.items():
        if not replace_existing_msgs and pk in existing_series_pks:
            continue
        series_card = get_uploaded_series_card(
            pk,
            series,
            existing_series_pks,
            replace_existing_msgs,
        )
        upload_log.append(series_card)
    return upload_log


def get_uploaded_series_card(
    pk: int,
    series: TgMessageSeries,
    existing_series_pks: dict[int, TgMessageSeries],
    replace_existing_msgs: bool,
) -> dict[str, str]:
    series_card = {
        "namespace": series.namespace,
        "name": series.name,
        "pk": series.pk,
        "language_code": series.language_code,
    }
    if replace_existing_msgs and pk in existing_series_pks:
        series_card["processing_result"] = "🔵 Обновлено"
    else:
        series_card["processing_result"] = "🟢 Создано"
    return series_card


def get_archived_messages(queryset: QuerySet) -> bytes:
    serialized_msgs_series = serializers.serialize(
        format='json',
        queryset=queryset,
        indent=4,
    )
    msgs_series = [series for series in queryset]

    _, serialized_texts_msgs = get_serialized_msgs(
        TgTextMessage, msgs_series,
    )
    images_msgs, serialized_images_msgs = get_serialized_msgs(
        TgImageMessage, msgs_series,
    )
    docs_msgs, serialized_docs_msgs = get_serialized_msgs(
        TgDocumentMessage, msgs_series,
    )
    _, serialized_inline_buttons = get_serialized_msgs(
        TgInlineButton, msgs_series,
    )

    with BytesIO() as bytes_io:
        with ZipFile(bytes_io, 'w') as zip_file:
            zip_file.writestr("msgs_series.json", serialized_msgs_series)
            zip_file.writestr("texts_msgs.json", serialized_texts_msgs)
            zip_file.writestr("images_msgs.json", serialized_images_msgs)
            zip_file.writestr("docs_msgs.json", serialized_docs_msgs)
            zip_file.writestr("inline_buttons.json", serialized_inline_buttons)
            for image_msg in images_msgs:
                image = image_msg.image
                zip_file.writestr(image.name, image.read())
            for doc_msg in docs_msgs:
                file = doc_msg.file
                zip_file.writestr(file.name, file.read())
        return bytes_io.getvalue()


def get_serialized_msgs(
    msg_model: type[models.Model],
    msgs_series: list[TgMessageSeries],
) -> tuple[QuerySet, str]:
    msgs = msg_model.objects.filter(
        series__in=msgs_series,
    )
    serialized_msgs = serializers.serialize(
        format='json',
        queryset=msgs,
        indent=4,
    )
    return msgs, serialized_msgs
