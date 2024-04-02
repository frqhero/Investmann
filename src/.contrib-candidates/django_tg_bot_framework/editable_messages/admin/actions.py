from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.admin.actions import delete_selected
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from .save_load_messages import get_archived_messages


@admin.action(description="Удалить выбранные Сообщения бота")
def delete_selected_messages(
    model_admin: ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
) -> TemplateResponse:
    template_response = delete_selected(model_admin, request, queryset)
    if not request.POST.get("post"):
        show_alarm = False
        active_series = []
        for series in queryset:
            if model_admin._is_alarm_needed(request, series):
                show_alarm = True
                active_series.append(series)

        template_response.context_data["show_alarm"] = show_alarm
        template_response.context_data["active_series"] = active_series

    return template_response


@admin.action(description='Снять отметку "Черновик"')
def make_active(
    model_admin: ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    queryset.update(draft=False)


@admin.action(description="Выгрузить сообщения")
def save_messages(
    model_admin: ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    content = get_archived_messages(queryset)
    response = HttpResponse(content, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=messages.zip'
    return response
