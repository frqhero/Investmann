from asgiref.sync import async_to_sync
import httpx
import pytest
from pytest_httpx import HTTPXMock

from auth.models import User


@pytest.mark.anyio()
async def test_httpx_mocking(
    httpx_mock: HTTPXMock,
):
    """Это демонстрация того, как можно тестировать запросы к API с помощью httpx и pytest-httpx."""
    httpx_mock.add_response(
        url='https://example.com/api/entities/1/',
        method='GET',
        content='Hello World!',
    )
    async with httpx.AsyncClient() as client:
        response = await client.get('https://example.com/api/entities/1/')
        response.raise_for_status()

    assert response.text == 'Hello World!'


@pytest.mark.django_db
def test_async_code_with_db_interaction():
    """Это демонстрация того, как можно тестировать взаимодействие с БД внутри асинхронного автотеста."""

    async def run_async_code(some_argument: str):
        users_count = await User.objects.acount()
        print('Users count in DB is', users_count)

    async_to_sync(run_async_code)(some_argument='fake-value')
