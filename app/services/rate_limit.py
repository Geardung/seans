import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_buckets: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_requests: int, window_sec: float):
    async def dependency(request: Request):
        key = request.client.host if request.client else "unknown"
        auth = request.headers.get("authorization")
        if auth:
            key = auth

        now = time.monotonic()
        bucket = _buckets[key]

        bucket[:] = [t for t in bucket if now - t < window_sec]

        if len(bucket) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        bucket.append(now)

    return dependency