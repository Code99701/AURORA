import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List
from fastapi import HTTPException, status


class InMemoryRateLimiter:
    """
    Thread-safe sliding-window rate limiter for sensitive endpoints.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._lock = Lock()
        self._records: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        error_message: str = "Too many requests. Please try again later.",
    ) -> None:
        if not self.enabled:
            return
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            # Purge timestamps older than the sliding window
            timestamps = [t for t in self._records[key] if t > cutoff]
            if len(timestamps) >= max_requests:
                retry_after = int(window_seconds - (now - timestamps[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error_message,
                    headers={"Retry-After": str(max(1, retry_after))},
                )
            timestamps.append(now)
            self._records[key] = timestamps

    def reset(self) -> None:
        """Clear all rate limit records. Used primarily in test suites."""
        with self._lock:
            self._records.clear()


auth_rate_limiter = InMemoryRateLimiter()
