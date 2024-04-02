from types import NoneType

import pydantic
import pytest
from django.db import connection

# FIXME should replace with separate model independent from Starter Pack code
from trigger_mailing.models import Lead
from yostate import Locator


@pytest.mark.django_db
def test_model_creation_with_locator():
    """Для записи полю достаточно присвоить новый инстанс Locator

    После чтения из БД в атрибуте нём сразу лежит инстанс Locator вместо словаря
    """  # noqa D400
    locator = Locator(
        state_class_locator='/not/exist/',
        params={
            'foo': 'bar',
        },
    )
    Lead.objects.create(
        tg_user_id=1,
        funnel_slug='first_mailing',
        state_machine_locator=locator,
    )

    test_lead = Lead.objects.get(
        tg_user_id=1,
        funnel_slug='first_mailing',
    )

    assert isinstance(test_lead.state_machine_locator, Locator)
    assert test_lead.state_machine_locator.state_class_locator == locator.state_class_locator
    assert test_lead.state_machine_locator.params == locator.params


@pytest.mark.django_db
def test_model_creation_with_json():
    json_raw = '{"state_class_locator": "/start-menu/", "params": {"foo": "bar"}}'
    locator = Locator.parse_raw(json_raw)
    Lead.objects.create(
        tg_user_id=1,
        funnel_slug='first_mailing',
        state_machine_locator=json_raw,
    )
    test_lead = Lead.objects.get(
        tg_user_id=1,
        funnel_slug='first_mailing',
    )
    assert isinstance(test_lead.state_machine_locator, Locator)
    assert test_lead.state_machine_locator.state_class_locator == locator.state_class_locator
    assert test_lead.state_machine_locator.params == locator.params


@pytest.mark.django_db
def test_model_creation_with_dict():
    obj = {
        "state_class_locator": "/start-menu/",
        "params": {
            "foo": "bar",
        },
    }
    locator = Locator.parse_obj(obj)
    Lead.objects.create(
        tg_user_id=1,
        funnel_slug='first_mailing',
        state_machine_locator=obj,
    )

    test_lead = Lead.objects.get(
        tg_user_id=1,
        funnel_slug='first_mailing',
    )
    assert isinstance(test_lead.state_machine_locator, Locator)
    assert test_lead.state_machine_locator.state_class_locator == locator.state_class_locator
    assert test_lead.state_machine_locator.params == locator.params


@pytest.mark.django_db
def test_locator_field_filtering(n=10):
    locator = Locator(
        state_class_locator='/mailing-queue/',
        params={
            'foo': 'bar',
        },
    )
    leads = [
        Lead(
            tg_user_id=tg_user_id,
            funnel_slug='first_mailing',
            state_machine_locator=locator,
        )
        for tg_user_id in range(n)
    ]

    Lead.objects.bulk_create(leads)
    leads_from_db = Lead.objects.filter(
        state_machine_locator__state_class_locator='/mailing-queue/',
    )
    assert len(leads_from_db) == n

    leads_from_db = Lead.objects.filter(
        state_machine_locator__params__foo='bar',
    )
    assert len(leads_from_db) == n


@pytest.mark.django_db
def test_model_creation_with_broken_input_data():
    obj = {
        "broken_state_class_locator": "/start-menu/",
    }
    with pytest.raises(pydantic.error_wrappers.ValidationError, match='state_class_locator'):
        Lead.objects.create(
            tg_user_id=1,
            funnel_slug='first_mailing',
            state_machine_locator=obj,
        )

    json_raw = '{"broken_state_class_locator": "/start-menu/"}'
    with pytest.raises(pydantic.error_wrappers.ValidationError, match='state_class_locator'):
        Lead.objects.create(
            tg_user_id=1,
            funnel_slug='first_mailing',
            state_machine_locator=json_raw,
        )


@pytest.mark.django_db
def test_broken_db_data():
    cursor = connection.cursor()
    query = ("INSERT INTO trigger_mailing_lead "
             "(tg_user_id, funnel_slug, state_machine_locator, "
             "mailing_failure_reason_code, mailing_failure_description, mailing_failure_debug_details) "
             "VALUES (2, 'first_mailing', '{\"garbage\": true}', '', '', '')")
    cursor.execute(query)

    test_lead = Lead.objects.get(
        tg_user_id=2,
        funnel_slug='first_mailing',
    )
    assert isinstance(test_lead.state_machine_locator, NoneType)
