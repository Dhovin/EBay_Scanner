import pytest
from app.services.notifier import Notifier


@pytest.mark.asyncio
async def test_invalid_service_test_notification():
    res = await Notifier.send_test_notification("invalid_service", "http://example.com")
    assert not res["success"]
    assert "Unsupported" in res["message"]
