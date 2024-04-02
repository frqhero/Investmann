from typing import Generator, Type, Iterable

from django.db.models import QuerySet

from mysent import MessageLocator, MessageRouter
from .models import TgMessageSeries, AbstractTgMessage, TgInlineButton

CallbackData = str
LanguageCode = str


class LocatorsCheckingResult(dict[LanguageCode, set[MessageLocator]]):

    def __contains__(self, series: TgMessageSeries):
        return series.message_locator in self.get(series.language_code, set())

    def __bool__(self):
        return any(self.values())

    def add_series(self, series: TgMessageSeries):
        if series.language_code not in self.keys():
            self[series.language_code] = set()
        self[series.language_code].add(series.message_locator)


class ButtonsCheckingResult(dict[LanguageCode, dict[MessageLocator, set[CallbackData]]]):

    def __contains__(self, series: TgMessageSeries):
        return bool(self.get_for_series(series))

    def __bool__(self):
        return any((buttons_data.values() for buttons_data in self.values()))

    def add(self, locator: MessageLocator, missed_button: tuple[LanguageCode, CallbackData]):
        language, callback = missed_button
        if language not in self.keys():
            self[language] = dict()
        if locator not in self[language]:
            self[language][locator] = set()
        self[language][locator].add(callback)

    def get_for_series(self, series: TgMessageSeries):
        bad_buttons_data = self.get(series.language_code, dict())
        bad_callbacks = bad_buttons_data.get(series.message_locator, set())
        return bad_callbacks


class DbStatement:

    def __init__(
        self,
        message_router: MessageRouter,
        language_codes: Iterable[str],
        *,
        series_model: Type[TgMessageSeries] = TgMessageSeries,
    ):
        self.language_codes = language_codes
        self.series_model = series_model
        self.message_router = message_router

        self.all_series: QuerySet[series_model] = series_model.objects.all()
        self._all_buttons_cache = None
        self._all_messages_cache = None
        self.expected = self._get_expected()
        self._missed_cache = None
        self._drafts_cache = None
        self._active_cache = None
        self._redundant_cache = None
        self._empty_cache = None
        self._missed_buttons_cache = None
        self._bad_cache = None
        self._good_cache = None

    # Все ниже следующие property нужны, чтобы запросы к базе не отправлялись при инициализации
    # иначе сборка образа будет взрываться на collectstatic

    @property
    def drafts(self):
        if self._drafts_cache is None:
            self._sort_series()
        return self._drafts_cache

    @property
    def active(self):
        if self._active_cache is None:
            self._sort_series()
        return self._active_cache

    @property
    def redundant(self):
        if self._redundant_cache is None:
            self._sort_series()
        return self._redundant_cache

    @property
    def empty(self):
        if self._empty_cache is None:
            self._sort_series()
        return self._empty_cache

    @property
    def missed_buttons(self):
        if self._missed_buttons_cache is None:
            self._sort_series()
        return self._missed_buttons_cache

    @property
    def bad(self):
        if self._bad_cache is None:
            self._sort_series()
        return self._bad_cache

    @property
    def good(self):
        if self._good_cache is None:
            self._sort_series()
        return self._good_cache

    @property
    def missed(self):
        if self._missed_cache is None:
            self._missed_cache = LocatorsCheckingResult()
            for language_code in self.language_codes:
                not_draft_locators = {
                    series.message_locator
                    for series in self.all_series
                    if not series.draft and series.language_code == language_code
                }
                self._missed_cache[language_code] = self.expected[language_code] - not_draft_locators
        return self._missed_cache

    @property
    def all_messages(self) -> Generator[AbstractTgMessage, None, None]:
        if self._all_messages_cache is None:
            self._all_messages_cache = [
                message
                for model in self.series_model.message_models
                for message in model.objects.all().select_related('series')
            ]
        return self._all_messages_cache

    @property
    def all_buttons(self) -> Generator[TgInlineButton, None, None]:
        if self._all_buttons_cache is None:
            self._all_buttons_cache = [
                button
                for model in self.series_model.button_models
                for button in model.objects.all().select_related('series')
            ]
        return self._all_buttons_cache

    def _get_expected(self) -> LocatorsCheckingResult:
        """Локаторы серий, которые ожидает роутер сообщений."""
        expected_series = LocatorsCheckingResult()
        for language_code in self.language_codes:
            expected_locators = {
                locator
                for locator, contract in self.message_router.items()
                if contract.languages is None or language_code in contract.languages
            }
            expected_series[language_code] = expected_locators
        return expected_series

    def _sort_series(self):
        self._drafts_cache = LocatorsCheckingResult()
        self._active_cache = LocatorsCheckingResult()
        self._redundant_cache = LocatorsCheckingResult()
        self._empty_cache = LocatorsCheckingResult()
        self._missed_buttons_cache = ButtonsCheckingResult()
        self._bad_cache = LocatorsCheckingResult()
        self._good_cache = LocatorsCheckingResult()
        for series in self.all_series:
            self._sort_by_status(series)
            self._check_series_for_troubles(series)

    def _sort_by_status(self, series: TgMessageSeries):
        if series.draft:
            self._drafts_cache.add_series(series)
        if series in self.expected and not series.draft:
            self._active_cache.add_series(series)
        if series not in self.expected:
            self._redundant_cache.add_series(series)

    def _check_series_for_troubles(self, series: TgMessageSeries):
        series_messages = filter(
            lambda msg: msg.series == series,
            self.all_messages,
        )
        if not next(series_messages, None):
            self._empty_cache.add_series(series)

        for button in self._get_missed_buttons(series):
            self._missed_buttons_cache.add(series.message_locator, button)

        if series not in self._active_cache:
            return

        if (
            series in self._empty_cache
            or series in self._missed_buttons_cache
        ):
            self._bad_cache.add_series(series)
        else:
            self._good_cache.add_series(series)

    def _get_missed_buttons(self, series: TgMessageSeries) -> set[tuple[LanguageCode, CallbackData]]:
        message_contract = self.message_router.get(series.message_locator, language=series.language_code)
        if not message_contract or not message_contract.buttons:
            return set()

        expected_buttons = {
            (series.language_code, button.action)
            for button in message_contract.get_buttons(series.language_code)
        }
        series_buttons = self._get_series_buttons(series)
        return expected_buttons - series_buttons

    def _get_series_buttons(self, series: TgMessageSeries) -> set[tuple[LanguageCode, CallbackData]]:
        series_message_numbers = {
            message.message_order
            for message in self.all_messages
            if message.series == series
        }
        return {
            (series.language_code, button.callback_data)
            for button in self.all_buttons
            if button.series == series and button.message_number in series_message_numbers
        }
