from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from mysent import MessageLocator

PARSE_MODE_MAX_LENGTH = 16
NAMESPACE_MAX_LENGTH = 200
NAME_MAX_LENGTH = 100
LANGUAGE_CODE_MAX_LENGTH = 6


class AbstractTgMessage(models.Model):
    protect_content = models.BooleanField(
        'Защищенное сообщение',
        default=False,
        help_text='Запретить пересылать сообщение и сохранять его содержимое',
    )
    series = models.ForeignKey(
        'TgMessageSeries',
        on_delete=models.CASCADE,
    )
    message_order = models.PositiveSmallIntegerField(
        'Номер в серии',
        default=0,
        help_text='При отправке нескольких сообщений, они будут отправлены в порядке своих номеров',
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f'#{self.message_order}'


class TgTextMessage(AbstractTgMessage):
    class ParseMode(models.TextChoices):
        NONE = ('', 'Не используется')
        HTML = ('HTML', 'HTML')
        Markdown = ('Markdown', 'Markdown')

    text = models.TextField('Текст')
    disable_web_page_preview = models.BooleanField(
        'Отключить предпросмотр ссылок',
        default=False,
        help_text='Предпросмотр ссылок - это отображение содержимого сайта в теле сообщения',
    )
    parse_mode = models.CharField(
        'Форматирование',
        max_length=PARSE_MODE_MAX_LENGTH,
        blank=True,
        choices=ParseMode.choices,
        default=ParseMode.NONE,
    )

    class Meta:
        verbose_name = 'Текстовое сообщение'
        verbose_name_plural = 'Текстовые сообщения'


class TgImageMessage(AbstractTgMessage):
    image = models.ImageField('Картинка')
    has_spoiler = models.BooleanField('Спойлер', default=False)

    class Meta:
        verbose_name = 'Сообщение с картинкой'
        verbose_name_plural = 'Сообщения с картинками'


class TgDocumentMessage(AbstractTgMessage):
    file = models.FileField('Документ')
    disable_content_type_detection = models.BooleanField(
        'Не проверять тип файла',
        default=False,
        help_text='Отключение автоматического определения типа содержимого файла на стороне сервера.',
    )

    class Meta:
        verbose_name = 'Сообщение с документом'
        verbose_name_plural = 'Сообщения с документами'


class TgInlineButton(models.Model):
    text = models.CharField(
        'Текст кнопки',
        max_length=100,
    )
    callback_data = models.CharField(
        'callback data',
        blank=True,
        default='',
        max_length=64,
        help_text='Данные, отправляемые боту при нажатии кнопки. Не может быть заполнено одновременно с url',
    )
    url = models.URLField(
        'URL',
        blank=True,
        default='',
        help_text='Ссылка для перехода при нажатии. Не может быть заполнено одновременно с callback data',
    )
    series = models.ForeignKey(
        'TgMessageSeries',
        on_delete=models.CASCADE,
        related_name='inline_buttons',
    )
    message_number = models.PositiveSmallIntegerField(
        'Номер сообщения',
        null=True,
        blank=True,
        help_text='Номер сообщения в серии, к которому будет привязана кнопка',
    )
    row = models.SmallIntegerField(
        'Ряд в клавиатуре',
    )
    position_in_row = models.SmallIntegerField(
        'Место в ряду',
    )

    class Meta:
        verbose_name = 'Инлайн кнопка'
        verbose_name_plural = 'Инлайн кнопки'

    def __str__(self):
        return f'Inline button: {self.row} | {self.position_in_row}'

    def clean(self):
        if self.callback_data and self.url:
            raise ValidationError(_("У кнопки может только одно из значений: 'callback_data' либо 'url'"))
        if not self.callback_data and not self.url:
            raise ValidationError(_("У кнопки должно быть определено одно из значений: 'callback_data' либо 'url'"))


class TgMessageSeries(models.Model):
    message_models = [
        TgTextMessage,
        TgImageMessage,
        TgDocumentMessage,
    ]
    button_models = [
        TgInlineButton,
    ]

    namespace = models.CharField(
        'Адрес',
        max_length=NAMESPACE_MAX_LENGTH,
        help_text='Адрес в схеме сообщений позволяет избежать коллизий из-за одинаковых имён',
        db_index=True,
    )
    name = models.CharField(
        'Имя',
        max_length=NAME_MAX_LENGTH,
        help_text='Имя сообщения',
        db_index=True,
    )
    language_code = models.CharField(
        'Язык',
        max_length=8,
        help_text='Язык сообщения',
        db_index=True,
    )
    draft = models.BooleanField(
        'Черновик',
        default=False,
        db_index=True,
        help_text='Черновик не используется в работе бота',
    )
    disable_notification = models.BooleanField(
        'Отправить тихо',
        default=False,
        help_text='Пользователи получат уведомление без звука.',
    )

    class Meta:
        unique_together = ('namespace', 'name', 'language_code')
        verbose_name = 'Сообщение бота'
        verbose_name_plural = 'Сообщения бота'
        permissions = [
            ("can_change_ready_messages", "Can change ready messages"),
        ]

    @property
    def message_locator(self):
        return MessageLocator(
            str(self.namespace),
            str(self.name),
        )

    def __str__(self):
        return str(self.message_locator)
