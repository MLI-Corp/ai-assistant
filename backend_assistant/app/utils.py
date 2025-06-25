import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Coroutine

logger = logging.getLogger(__name__)

DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 2 # Simple fixed delay

def retry_async(attempts: int = DEFAULT_RETRY_ATTEMPTS, delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS):
    """
    A decorator for retrying an async function if it raises an exception.
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    function_name = func.__name__
                    if attempt < attempts:
                        logger.warning(
                            f"Attempt {attempt}/{attempts} for {function_name} failed with {type(e).__name__}: {e}. "
                            f"Retrying in {delay_seconds}s..."
                        )
                        await asyncio.sleep(delay_seconds)
                    else:
                        logger.error(
                            f"All {attempts} attempts for {function_name} failed. Last error: {type(e).__name__}: {e}",
                            exc_info=True if isinstance(e, (IOError, ConnectionError)) else False # Log stack for some errors
                        )
            if last_exception: # Should always be true if loop finished due to retries exhausted
                raise last_exception # Reraise the last caught exception
        return wrapper
    return decorator

# Example of how it might be used (not part of this file's direct execution):
# @retry_async(attempts=3, delay_seconds=1)
# async def fetch_url(session, url):
#     async with session.get(url) as response:
#         response.raise_for_status()
#         return await response.json()

if __name__ == '__main__':
    # Basic test for the retry decorator
    class MockSession:
        def __init__(self, fail_times=2):
            self.get_attempts = 0
            self.fail_times = fail_times

        async def get(self, url):
            self.get_attempts += 1
            print(f"MockSession.get called, attempt {self.get_attempts} for url {url}")
            if self.get_attempts <= self.fail_times:
                raise ConnectionError(f"Simulated connection error on attempt {self.get_attempts}")
            return {"data": "success", "url": url, "final_attempt": self.get_attempts}

    @retry_async(attempts=3, delay_seconds=0.1) # Quick delay for test
    async def test_fetch(session, url):
        print(f"Calling session.get for {url}")
        return await session.get(url)

    async def run_tests():
        logging.basicConfig(level=logging.INFO)

        # Test 1: Should succeed after retries
        print("\n--- Test 1: Expecting success after 2 failures ---")
        mock_session_success = MockSession(fail_times=2)
        try:
            result = await test_fetch(mock_session_success, "http://example.com/success")
            print(f"Test 1 Succeeded: {result}")
            assert result['final_attempt'] == 3
        except Exception as e:
            print(f"Test 1 Failed unexpectedly: {e}")

        # Test 2: Should fail after all retries
        print("\n--- Test 2: Expecting failure after 3 attempts ---")
        mock_session_fail = MockSession(fail_times=3)
        try:
            await test_fetch(mock_session_fail, "http://example.com/failure")
            print("Test 2 Succeeded unexpectedly (should have failed)")
        except ConnectionError as e:
            print(f"Test 2 Failed as expected: {e}")
            assert mock_session_fail.get_attempts == 3
        except Exception as e:
            print(f"Test 2 Failed with unexpected error: {e}")

        # Test 3: Should succeed on first attempt
        print("\n--- Test 3: Expecting success on first attempt ---")
        mock_session_first_success = MockSession(fail_times=0)
        try:
            result = await test_fetch(mock_session_first_success, "http://example.com/first_success")
            print(f"Test 3 Succeeded: {result}")
            assert result['final_attempt'] == 1
        except Exception as e:
            print(f"Test 3 Failed unexpectedly: {e}")


    asyncio.run(run_tests())
