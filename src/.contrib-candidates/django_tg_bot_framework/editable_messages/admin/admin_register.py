from functools import partial

from django.contrib import admin

from ..models import TgMessageSeries


def admin_register(admin_class=None, site=None):
    if admin_class is None:
        return partial(admin.register(TgMessageSeries, site=site))
    return admin.register(TgMessageSeries)(admin_class)
