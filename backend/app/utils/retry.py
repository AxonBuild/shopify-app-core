import asyncio
import logging
from typing import Callable, Awaitable, Type, Tuple

logger = logging.getLogger(__name__)


async def retry_async(
    fn: Callable[[], Awaitable],
    *,
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    label: str = "",
):
    """
    Retry an async callable up to `retries` times with exponential backoff.

    Args:
        fn:         Zero-argument async callable to retry.
        retries:    Maximum number of attempts (default 3).
        delay:      Initial wait time in seconds between attempts (default 1s).
        backoff:    Multiplier applied to delay after each failure (default 2x).
        exceptions: Tuple of exception types that trigger a retry.
        label:      Human-readable name for log messages.

    Returns:
        The return value of the first successful call.

    Raises:
        The last exception if all attempts are exhausted.

    Example::

        result = await retry_async(
            lambda: client.post(url, json=payload),
            retries=3,
            delay=1.0,
            exceptions=(httpx.RequestError, httpx.HTTPStatusError),
            label="WA platform send-message",
        )
    """
    last_exc: Exception | None = None
    wait = delay

    for attempt in range(1, retries + 1):
        try:
            return await fn()
        except exceptions as exc:
            last_exc = exc
            if attempt < retries:
                logger.warning(
                    "retry_async [%s] attempt %d/%d failed — %s. Retrying in %.1fs…",
                    label or "task", attempt, retries, exc, wait,
                )
                await asyncio.sleep(wait)
                wait *= backoff
            else:
                logger.error(
                    "retry_async [%s] all %d attempts exhausted — %s",
                    label or "task", retries, exc,
                )

    raise last_exc
