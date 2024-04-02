from django.db import models

from ..locator_field import LocatorField


class AbstractFunnelLeadModel(models.Model):
    tg_user_id = models.BigIntegerField(
        'Id юзера в Tg',
        db_index=True,
        help_text=(
            'Id пользователя Telegram. '
            'Пример значения: <code>123456789</code>.<br>'
            'Чтобы узнать ID пользователя, перешлите сообщение пользователя боту '
            '<a href="https://t.me/userinfobot">@userinfobot</a>.'
        ),
    )
    funnel_slug = models.SlugField(
        'воронка',
        db_index=True,
        help_text='Англоязычное название воронки, например "greeting_mailing". '
                  'Разрешены те же символы, что бывают внутри slug.',
    )
    state_machine_locator = LocatorField(
        'состояние',
        null=True,
        blank=True,
        help_text=(
            'Локатор состояния, в котором сейчас находится чат с пользователем. Заполняется автоматически. '
            'Используется стейт-машиной.<br>'
            'Пример значения: <code>{"state_class_locator": "/start-menu/"}</code>.<br>'
            'В поле хранится объект JSON в формате локатора из библиотеки '
            '<a href="https://pypi.org/project/yostate/">yostate</a>: '
            'атрибут <code>state_class_locator</code> указывает локатор класса состояния и похож на часть адреса URL, '
            'атрибут <code>params</code> задаёт параметры состояния.'
        ),
    )

    class Meta:
        abstract = True
        verbose_name = 'Лид'
        verbose_name_plural = 'Лиды'
        unique_together = [
            ['tg_user_id', 'funnel_slug'],
        ]

    def __str__(self):
        return f'Лид {self.id}'
