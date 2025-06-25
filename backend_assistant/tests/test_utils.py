import pytest
import asyncio
from unittest.mock import AsyncMock, call # For checking call count

from backend_assistant.app.utils import retry_async

@pytest.mark.asyncio
async def test_retry_async_success_on_first_try():
    mock_func = AsyncMock(return_value="success")

    @retry_async(attempts=3, delay_seconds=0.01)
    async def decorated_func():
        return await mock_func()

    result = await decorated_func()
    assert result == "success"
    mock_func.assert_called_once()


@pytest.mark.asyncio
async def test_retry_async_success_after_failures():
    mock_func = AsyncMock()
    mock_func.side_effect = [
        ConnectionError("Simulated error 1"),
        ConnectionError("Simulated error 2"),
        "success"
    ]

    @retry_async(attempts=3, delay_seconds=0.01)
    async def decorated_func():
        return await mock_func()

    result = await decorated_func()
    assert result == "success"
    assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_retry_async_failure_after_all_attempts():
    mock_func = AsyncMock()
    mock_func.side_effect = [
        ConnectionError("Simulated error 1"),
        ConnectionError("Simulated error 2"),
        ConnectionError("Simulated error 3"),
        ConnectionError("Simulated error 4") # Should not be called if attempts=3
    ]

    @retry_async(attempts=3, delay_seconds=0.01)
    async def decorated_func():
        return await mock_func()

    with pytest.raises(ConnectionError, match="Simulated error 3"):
        await decorated_func()

    assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_retry_async_passes_args_and_kwargs():
    mock_func = AsyncMock(return_value="processed")

    @retry_async(attempts=2, delay_seconds=0.01)
    async def decorated_func(*args, **kwargs):
        return await mock_func(*args, **kwargs)

    arg1, kwarg1 = "test_arg", "test_kwarg"
    result = await decorated_func(arg1, kw_arg=kwarg1)

    assert result == "processed"
    mock_func.assert_called_once_with(arg1, kw_arg=kwarg1)

# To run these tests, navigate to `backend_assistant` directory and run `pytest`
# Ensure pytest and any other test dependencies (like pytest-asyncio if not using built-in asyncio support)
# are installed in your environment (they are in pyproject.toml dev-dependencies).
