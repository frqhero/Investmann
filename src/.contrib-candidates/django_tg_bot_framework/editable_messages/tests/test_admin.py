from io import BytesIO

import pytest

from ..admin import EditableMessagesAdmin
from ..admin.save_load_messages import get_archived_messages, upload_messages
from ..models import TgMessageSeries, TgTextMessage, TgInlineButton


@pytest.mark.django_db
@pytest.mark.parametrize(
    "namespace, name, language_code, expected_status",
    [
        ("/", "normal", "ru", EditableMessagesAdmin.MessageStatus.GOOD),
        ("/", "draft", "ru", EditableMessagesAdmin.MessageStatus.DRAFT),
        ("/", "active_empty", "ru", EditableMessagesAdmin.MessageStatus.BAD),
        ("/", "missed_buttons", "ru", EditableMessagesAdmin.MessageStatus.BAD),
        ("/", "missed_button_link", "ru", EditableMessagesAdmin.MessageStatus.BAD),
        ("/", "redundant", "ru", EditableMessagesAdmin.MessageStatus.REDUNDANT),
    ],
)
def test_series_getting_status(
    admin_site,
    namespace,
    name,
    language_code,
    expected_status,
):
    series = TgMessageSeries.objects.get(
        namespace=namespace,
        name=name,
        language_code=language_code,
    )
    message_status = admin_site.get_status(series)
    assert message_status == expected_status


@pytest.mark.django_db
@pytest.mark.parametrize(
    "namespace, name, language_code, expected_sense",
    [
        ("/", "normal", "ru", "normal"),
        ("/", "redundant", "ru", None),
    ],
)
def test_series_getting_sense(admin_site, namespace, name, language_code, expected_sense):
    series = TgMessageSeries.objects.get(
        namespace=namespace,
        name=name,
        language_code=language_code,
    )
    message_sense = admin_site.show_sense(series)
    assert message_sense == expected_sense


@pytest.mark.django_db
@pytest.mark.parametrize(
    "namespace, name, language_code, expected_attributes",
    [
        ("/", "normal", "ru", "{{ foo }} - bar"),
        ("/", "draft", "ru", "в сообщении нет параметров"),
        ("/", "redundant", "ru", "в сообщении нет параметров"),
    ],
)
def test_series_getting_attributes(admin_site, namespace, name, language_code, expected_attributes):
    series = TgMessageSeries.objects.get(
        namespace=namespace,
        name=name,
        language_code=language_code,
    )
    message_attributes = admin_site.show_attributes(series)
    assert message_attributes == expected_attributes


@pytest.mark.django_db
def test_messages_upload():
    """Test saving and uploading messages.

    User:
      - save messages
      - upload messages
    """
    namespace = "test-namespace"
    name = "test_name"
    language_code = 'ru_ru'
    text = "test text"
    inline_button_text = "test inline button text"
    test_url = "https://example.com/"
    series = TgMessageSeries.objects.create(
        namespace=namespace,
        name=name,
        language_code=language_code,
    )
    TgTextMessage.objects.create(
        text=text,
        series=series,
    )
    TgInlineButton.objects.create(
        text=inline_button_text,
        url=test_url,
        series=series,
        message_number=0,
        row=1,
        position_in_row=1,
    )
    queryset = TgMessageSeries.objects.all()
    content = get_archived_messages(queryset)
    series.delete()
    bytes_io = BytesIO(content)
    upload_messages(bytes_io, replace_existing_msgs=False)
    upload_messages(bytes_io, replace_existing_msgs=True)
    series = TgMessageSeries.objects.get(
        namespace=namespace,
        name=name,
        language_code=language_code,
    )
    text_msg = TgTextMessage.objects.get(
        text=text,
        series=series,
    )
    inline_button = TgInlineButton.objects.get(
        text=inline_button_text,
        series=series,
        url=test_url,
    )
    assert series.namespace == namespace
    assert text_msg.text == text
    assert inline_button.text == inline_button_text
