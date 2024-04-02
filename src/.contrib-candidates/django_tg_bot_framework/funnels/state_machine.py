from collections import ChainMap
from contextlib import contextmanager
from contextvars import ContextVar, Token
from functools import reduce
import logging
from typing import Callable, final, Type, NamedTuple, TypeVar

from pydantic import validate_arguments, ValidationError
from yostate import Router, Crawler, Locator, LocatorError

from django.db import transaction, models

from .models import AbstractFunnelLeadModel
from .events import AbstractFunnelEvent

logger = logging.getLogger('django_tg_bot_framework')


class LeadNaturalId(NamedTuple):
    tg_user_id: int
    funnel_slug: str


FunnelLeadModel = TypeVar('FunnelLeadModel', bound=AbstractFunnelLeadModel)


def _create_crawler(*, lead: AbstractFunnelLeadModel, router: Router) -> Crawler:
    crawler = Crawler(router=router)

    if lead.state_machine_locator:
        try:
            crawler.restore(lead.state_machine_locator)
        except ValidationError:
            logger.warning(
                'Reset invalid state locator of funnel lead tg_user_id=%s',
                lead.tg_user_id,
            )
        except LocatorError:
            logger.warning(
                'Reset not found state locator of funnel lead tg_user_id=%s',
                lead.tg_user_id,
            )

    return crawler


@contextmanager
@transaction.atomic()
def _work_with_leads(lead_natural_ids: list[LeadNaturalId], *, lead_model: Type[FunnelLeadModel]) -> tuple[
    dict[LeadNaturalId, FunnelLeadModel],
    dict[LeadNaturalId, FunnelLeadModel],
    dict[LeadNaturalId, FunnelLeadModel],
]:
    filter_conditions = [
        models.Q(tg_user_id=natural_id.tg_user_id, funnel_slug=natural_id.funnel_slug)
        for natural_id in lead_natural_ids
    ]

    old_lead_mapping: dict[LeadNaturalId, FunnelLeadModel] = {}

    if filter_conditions:
        filter_condition = reduce(lambda a, b: a | b, filter_conditions)
        leads_affected = (
            lead_model.objects
            .select_for_update()  # lock record till processing end
            .filter(filter_condition)
        )
        old_lead_mapping = {
            LeadNaturalId(lead.tg_user_id, lead.funnel_slug): lead
            for lead in leads_affected
        }

    new_lead_mapping: dict[LeadNaturalId, FunnelLeadModel] = {}
    lead_mapping: ChainMap[LeadNaturalId, FunnelLeadModel] = ChainMap(
        old_lead_mapping,
        new_lead_mapping,
    )

    yield old_lead_mapping, new_lead_mapping, lead_mapping

    # save lead states to db if no exceptions occur during processing
    if old_lead_mapping:
        lead_model.objects.bulk_update(
            old_lead_mapping.values(),
            fields=['state_machine_locator'],
        )

    if new_lead_mapping:
        lead_model.objects.bulk_create(
            new_lead_mapping.values(),
        )


@final
class FunnelStateMachine:
    get_router_by_funnel_slug: Callable[[str], Router | None]
    lead_model: Type[FunnelLeadModel]
    _unprocessed_events_queue: ContextVar[list[AbstractFunnelEvent]]

    class OuterPushError(RuntimeError):
        def __init__(
            self,
            msg='Can`t push event outside of `process_collected` context manager call.',
            *args,
            **kwargs,
        ):
            super().__init__(msg, *args, **kwargs)

    @validate_arguments
    def __init__(
        self,
        *,
        router_mapping: dict[str, Router] | Callable[[str], Router],
        lead_model: Type[FunnelLeadModel],
    ):
        self.get_router_by_funnel_slug = router_mapping if callable(router_mapping) else router_mapping.get
        self.lead_model = lead_model
        self._unprocessed_events_queue = ContextVar('_unprocessed_events_queue')

    @validate_arguments
    def process_many(self, events: list[AbstractFunnelEvent]) -> None:
        """Restore leads from db, process funnel events and save leads to db."""
        tasks: list[tuple[LeadNaturalId, AbstractFunnelEvent, Router | None]] = [
            (
                LeadNaturalId(tg_user_id=event.tg_user_id, funnel_slug=event.funnel_slug),
                event,
                self.get_router_by_funnel_slug(event.funnel_slug),
            )
            for event in events
        ]
        filtered_tasks: list[tuple[LeadNaturalId, AbstractFunnelEvent, Router]] = [
            (lead_natural_id, event, router) for lead_natural_id, event, router in tasks if router
        ]
        affected_lead_ids = [lead_natural_id for lead_natural_id, *_ in filtered_tasks]

        with _work_with_leads(affected_lead_ids, lead_model=self.lead_model) as (_, new_lead_mapping, lead_mapping):
            for lead_natural_id, event, router in filtered_tasks:
                lead = lead_mapping.get(lead_natural_id)

                if not lead:
                    lead = self.lead_model(
                        tg_user_id=lead_natural_id.tg_user_id,
                        funnel_slug=lead_natural_id.funnel_slug,
                    )
                    new_lead_mapping[lead_natural_id] = lead

                crawler = _create_crawler(lead=lead, router=router)

                if not crawler.attached:
                    crawler.switch_to(Locator('/'))

                crawler.process(event)

                lead.state_machine_locator = crawler.current_state.locator

    @contextmanager
    def process_collected(self):
        """Initialize contextvar to collect funnel events, process them and update db on context exit."""
        var_token: Token = self._unprocessed_events_queue.set([])
        try:
            events_to_proccess = self._unprocessed_events_queue.get()
            yield events_to_proccess
        finally:
            self._unprocessed_events_queue.reset(var_token)

        if events_to_proccess:
            self.process_many(events_to_proccess)

    @validate_arguments
    def push_event(self, event: AbstractFunnelEvent) -> None:
        """Push event to unprocessed events queue.

        Should be used only inside `process_collected` context manager call.
        """
        queue = self._unprocessed_events_queue.get(None)

        if queue is None:
            raise self.OuterPushError()

        queue.append(event)

    @validate_arguments
    def push_events(self, events: list[AbstractFunnelEvent]) -> None:
        """Push events to unprocessed events queue.

        Should be used only inside `process_collected` context manager call.
        """
        queue = self._unprocessed_events_queue.get(None)

        if queue is None:
            raise self.OuterPushError()

        queue.extend(events)

    @validate_arguments
    def switch_to_many(self, transitions: list[tuple[LeadNaturalId, Locator]]) -> None:
        """Restore leads from db, switch to new state locator and save leads to db."""
        tasks: list[tuple[LeadNaturalId, Locator, Router | None]] = [
            (natural_lead_id, locator, self.get_router_by_funnel_slug(natural_lead_id.funnel_slug))
            for natural_lead_id, locator in transitions
        ]
        filtered_tasks: list[tuple[LeadNaturalId, Locator, Router]] = [
            (natural_lead_id, locator, router)
            for natural_lead_id, locator, router in tasks
            if router
        ]
        affected_lead_ids = {natural_lead_id for natural_lead_id, *_ in filtered_tasks}
        with _work_with_leads(affected_lead_ids, lead_model=self.lead_model) as (_, new_lead_mapping, lead_mapping):
            for natural_lead_id, locator, router in filtered_tasks:
                lead = lead_mapping.get(natural_lead_id)

                if not lead:
                    lead = self.lead_model(
                        tg_user_id=natural_lead_id.tg_user_id,
                        funnel_slug=natural_lead_id.funnel_slug,
                    )
                    new_lead_mapping[natural_lead_id] = lead

                crawler = _create_crawler(lead=lead, router=router)
                crawler.switch_to(locator)

                lead.state_machine_locator = crawler.current_state.locator
