import pytest

from mysent import MessageLocator
from ..db_checker import DbStatement

message_locator_missed = MessageLocator('/', 'missed')
message_locator_normal = MessageLocator('/', 'normal')
message_locator_missed_only_ru = MessageLocator('/', 'missed_only_ru')
message_locator_only_ru_button = MessageLocator('/', 'only_ru_button')
message_locator_draft = MessageLocator('/', 'draft')
message_locator_active_empty = MessageLocator('/', 'active_empty')
message_locator_redundant_empty = MessageLocator('/', 'redundant_empty')
message_locator_missed_buttons = MessageLocator('/', 'missed_buttons')
message_locator_missed_button_link = MessageLocator('/', 'missed_button_link')
message_locator_redundant = MessageLocator('/', 'redundant')
message_locator_redundant_draft = MessageLocator('/', 'redundant_draft')


@pytest.mark.django_db
@pytest.mark.parametrize(
    "checking_result_name, language, locators",
    [
        ('active', 'ru', {message_locator_normal,
                          message_locator_only_ru_button,
                          message_locator_active_empty,
                          message_locator_missed_buttons,
                          message_locator_missed_button_link}),
        ('missed', 'ru', {message_locator_missed,
                          message_locator_draft,
                          message_locator_missed_only_ru}),
        ('missed_buttons', 'ru', {message_locator_missed_buttons: {'foo'},
                                  message_locator_missed_button_link: {'foo'}}),
        ('missed_buttons', 'en', None),
        ('bad', 'ru', {message_locator_missed_buttons,
                       message_locator_missed_button_link,
                       message_locator_active_empty}),
        ('bad', 'en', None),
        ('good', 'ru', {message_locator_normal,
                        message_locator_only_ru_button}),
        ('good', 'en', {message_locator_only_ru_button}),
        ('drafts', 'ru', {message_locator_draft,
                          message_locator_redundant_draft}),
        ('empty', 'ru', {message_locator_active_empty,
                         message_locator_redundant_empty,
                         message_locator_redundant_draft}),
        ('redundant', 'ru', {message_locator_redundant,
                             message_locator_redundant_empty,
                             message_locator_redundant_draft}),
    ],
)
def test_db_statement(checking_result_name, language, locators, pre_filled_db, pre_filled_message_router):
    db_statement = DbStatement(message_router=pre_filled_message_router, language_codes=['ru', 'en'])
    checking_result = getattr(db_statement, checking_result_name)
    assert checking_result.get(language) == locators
