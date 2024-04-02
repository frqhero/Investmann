from django.contrib import admin


class TgEditableMessagesStatusFilter(admin.SimpleListFilter):
    title = 'Статус'
    parameter_name = 'status'

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        self.db_statement = model_admin.db_statement

    def lookups(self, request, model_admin):
        return (
            ('good', model_admin.MessageStatus.GOOD.value),
            ('redundant', model_admin.MessageStatus.REDUNDANT.value),
            ('draft', model_admin.MessageStatus.DRAFT.value),
            ('bad', model_admin.MessageStatus.BAD.value),
        )

    def queryset(self, request, queryset):
        if self.value() == 'draft':
            return queryset.filter(draft=True)

        redundant_pks, bad_pks, good_pks = self._sort_pks(queryset)
        queryset_mapping = {
            'bad': queryset.filter(pk__in=bad_pks),
            'good': queryset.filter(pk__in=good_pks),
            'redundant': queryset.filter(pk__in=redundant_pks),
        }
        return queryset_mapping.get(self.value(), queryset)

    def _sort_pks(self, all_series) -> tuple[list, list, list]:
        redundant_pks = []
        bad_pks = []
        good_pks = []
        for series in all_series:
            if series in self.db_statement.redundant:
                redundant_pks.append(series.pk)
            if series in self.db_statement.bad:
                bad_pks.append(series.pk)
            if series in self.db_statement.good:
                good_pks.append(series.pk)
        return redundant_pks, bad_pks, good_pks


class TgEditableMessagesLanguageFilter(admin.SimpleListFilter):
    title = 'Язык'
    parameter_name = 'language_code'

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        self.db_statement = model_admin.db_statement

    def lookups(self, request, model_admin):
        language_code_values = model_admin.model.objects.all().values('language_code').distinct()
        language_codes = (
            value['language_code']
            for value in language_code_values
        )
        return [
            (language_code, model_admin.languages.get(language_code, language_code))
            for language_code in language_codes
        ]

    def queryset(self, request, queryset):
        if language_code := self.value():
            return queryset.filter(language_code=language_code)
