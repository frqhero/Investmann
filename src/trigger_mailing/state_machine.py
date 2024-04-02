from django_tg_bot_framework.funnels import FunnelStateMachine

from .models import Lead
from .funnels import (
    single_mailing_router,
    FIRST_MAILING_FUNNEL_SLUG,
    SECOND_MAILING_FUNNEL_SLUG,
)


state_machine = FunnelStateMachine(
    router_mapping={
        FIRST_MAILING_FUNNEL_SLUG: single_mailing_router,
        SECOND_MAILING_FUNNEL_SLUG: single_mailing_router,
    },
    lead_model=Lead,
)
