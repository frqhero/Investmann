from typing import Any
import pytest


@pytest.fixture()
def anyio_backend() -> tuple[str, dict[str, Any]]:
    """Configure anyio pytest backend to test with asyncio event loop only."""
    return "asyncio", {"use_uvloop": True}
