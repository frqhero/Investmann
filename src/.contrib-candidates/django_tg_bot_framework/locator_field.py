from contextlib import suppress

from django import forms
from django.core import exceptions
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_json_widget.widgets import JSONEditorWidget
from pydantic import ValidationError

from yostate import Locator


class LocatorFormField(forms.JSONField):
    default_error_messages = {
        "invalid": _("Enter a valid Locator data."),
    }

    widget = JSONEditorWidget

    def widget_attrs(self, widget):
        return {
            'style': 'width: 100%; max-width: 1000px; display:inline-block; height:250px;',
        }

    def prepare_value(self, value):
        if isinstance(value, Locator):
            value = value.dict(by_alias=True)
        return super().prepare_value(value)

    def to_python(self, value):
        if isinstance(value, Locator):
            return value.dict(by_alias=True)
        return value

    def validate(self, value):
        super().validate(value)
        try:
            if isinstance(value, str):
                Locator.parse_raw(value)
            if isinstance(value, dict):
                Locator.parse_obj(value)
        except ValidationError:
            raise exceptions.ValidationError(
                self.error_messages["invalid"],
                code="invalid",
                params={"value": value},
            ) from None


class LocatorField(models.JSONField):
    description = 'Field represents Locator class from Yostate'
    default_error_messages = {
        'invalid': _('Value must be Locator.'),
    }
    _default_hint = ('Locator',)

    def from_db_value(self, value, expression, connection) -> Locator | None:
        value = super().from_db_value(value, expression, connection)
        if isinstance(value, dict):
            with suppress(ValidationError):
                return Locator.parse_obj(value)
        #  В случае проблем с получением данных по текущему локатору пользователя
        #  просто сбрасываем его, а пользователя отправляем в главное меню.

    def to_python(self, value):
        if isinstance(value, Locator):
            return value.dict(by_alias=True)
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, Locator):
            value = value.dict(by_alias=True)
        if isinstance(value, str) and not prepared:
            value = Locator.parse_raw(value).dict(by_alias=True)
        if isinstance(value, dict):
            value = Locator.parse_obj(value).dict(by_alias=True)
        return super().get_db_prep_value(value, connection, prepared)

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "form_class": LocatorFormField,
                **kwargs,
            },
        )
