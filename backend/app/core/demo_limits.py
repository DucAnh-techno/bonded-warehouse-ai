"""Small anonymous demo: one process, bounded shared AI budget."""
import time
from collections import deque
from threading import Lock
from fastapi import HTTPException
from app.core.config import settings

_calls: deque[float] = deque()
_lock = Lock()


def extraction_budget() -> None:
    if not settings.DEMO_ONLY:
        return
    now = time.monotonic()
    with _lock:
        while _calls and now - _calls[0] >= 3600:
            _calls.popleft()
        if len(_calls) >= settings.DEMO_AI_REQUESTS_PER_HOUR:
            raise HTTPException(429, "Bản demo đã đạt giới hạn trích xuất trong giờ này. Vui lòng thử lại sau.", headers={"Retry-After": "3600"})
        _calls.append(now)
