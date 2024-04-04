from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    readonly_fields = ["get_image_preview"]
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            'Photo',
            {
                'fields': (
                    'image',
                    'get_image_preview',
                ),
            },
        ),
    )

    def get_image_preview(self, obj):
        if not obj.image:
            return 'выберите картинку'
        return format_html(
            '<img src="{url}" style="max-height: 200px;"/>',
            url=obj.image.url,
        )
    get_image_preview.short_description = 'превью'

    class Media:
        css = {
            'all': [
                'admin/sticky-save.css',
            ],
        }
        js = [
            'admin/save-hotkey.js',
        ]
