from yostate import Crawler, Locator

from django_tg_bot_framework.funnels import AbstractFunnelEvent

from .. import (
    single_mailing_router,
    LeadNavigatedToMainMenu,
    LeadLaunchedSecondMailing,
    LeadUnsubscribed,
    MailingWasSentToLead,
    MailingTargetActionAcceptedByLead,
    FIRST_MAILING_FUNNEL_SLUG,
    SECOND_MAILING_FUNNEL_SLUG,
)


def test_first_mailing_funnel_start_to_end_accept_traversing():
    crawler = Crawler(router=single_mailing_router)

    crawler.switch_to(Locator('/'))
    assert crawler.attached

    with AbstractFunnelEvent.set_default_tg_user_id(99):
        crawler.process(LeadNavigatedToMainMenu())
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/mailing-queue/'
        assert current_locator.params.get('added_to_queue_at')

        crawler.process(MailingWasSentToLead(funnel_slug=FIRST_MAILING_FUNNEL_SLUG))
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/message-sent/'
        assert current_locator.params.get('message_sent_at')

        crawler.process(
            MailingTargetActionAcceptedByLead(
                funnel_slug=FIRST_MAILING_FUNNEL_SLUG,
                action='buy_anything',
            ),
        )
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/button-pressed/'
        assert current_locator.params.get('accepted_at')
        assert current_locator.params.get('action_selected') == 'buy_anything'


def test_first_mailing_funnel_start_to_end_unsubscribe_traversing():
    crawler = Crawler(router=single_mailing_router)

    crawler.switch_to(Locator('/'))
    assert crawler.attached

    with AbstractFunnelEvent.set_default_tg_user_id(99):
        crawler.process(LeadNavigatedToMainMenu())
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/mailing-queue/'
        assert current_locator.params.get('added_to_queue_at')

        crawler.process(MailingWasSentToLead(funnel_slug=FIRST_MAILING_FUNNEL_SLUG))
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/message-sent/'
        assert current_locator.params.get('message_sent_at')

        crawler.process(LeadUnsubscribed(funnel_slug=FIRST_MAILING_FUNNEL_SLUG))
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/unsubscribed/'


def test_second_mailing_funnel_start_to_end_accept_traversing():
    crawler = Crawler(router=single_mailing_router)

    crawler.switch_to(Locator('/'))
    assert crawler.attached

    with AbstractFunnelEvent.set_default_tg_user_id(99):
        crawler.process(LeadLaunchedSecondMailing())
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/mailing-queue/'
        assert current_locator.params.get('added_to_queue_at')

        crawler.process(MailingWasSentToLead(funnel_slug=SECOND_MAILING_FUNNEL_SLUG))
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/message-sent/'
        assert current_locator.params.get('message_sent_at')

        crawler.process(
            MailingTargetActionAcceptedByLead(
                funnel_slug=SECOND_MAILING_FUNNEL_SLUG,
                action='buy_anything',
            ),
        )
        current_locator = crawler.current_state.locator
        assert current_locator.state_class_locator == '/button-pressed/'
        assert current_locator.params.get('accepted_at')
        assert current_locator.params.get('action_selected') == 'buy_anything'
