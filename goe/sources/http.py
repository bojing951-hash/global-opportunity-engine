"""Shared HTTP client: timeouts, retries with jitter, per-host rate limiting.

Every network call in this project goes through this module so that behaviour
under provider throttling is predictable and testable (no hidden retries in
adapter code). Adapters must not disable TLS verification; ``requests`` is
configured with the certifi bundle by ``goe`` import-time setup.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 goe-research/0.1"
)


@dataclass
class RetryPolicy:
    attempts: int = 3
    base_delay: float = 1.5
    max_delay: float = 30.0
    backoff: float = 2.0
    retry_status: tuple[int, ...] = (429, 500, 502, 503, 504)


@dataclass
class HostLimiter:
    """Token-bucket style minimum interval between calls to one host."""

    min_interval: float
    _last: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def wait(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            delay = self.min_interval - (now - last)
            if delay > 0:
                time.sleep(delay)
                now = time.monotonic()
            self._last[host] = now


class HttpClient:
    def __init__(
        self,
        timeout: float = 45.0,
        retry: RetryPolicy | None = None,
        min_interval: float = 0.4,
        session: requests.Session | None = None,
    ):
        self.timeout = timeout
        self.retry = retry or RetryPolicy()
        self.limiter = HostLimiter(min_interval)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_UA, "Accept-Encoding": "gzip, deflate"})

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        for attempt in range(1, self.retry.attempts + 1):
            self.limiter.wait(host)
            try:
                resp = self.session.request(method, url, **kwargs)
                if resp.status_code in self.retry.retry_status and attempt < self.retry.attempts:
                    self._sleep(attempt)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status not in (set(self.retry.retry_status) | {401, 403, 404}):
                    raise
                if status in {401, 403, 404}:
                    raise
                if attempt < self.retry.attempts:
                    self._sleep(attempt)
                    continue
                raise
        raise RuntimeError(f"request failed after retries: {url}") from last_exc

    def _sleep(self, attempt: int) -> None:
        delay = min(self.retry.max_delay, self.retry.base_delay * (self.retry.backoff ** (attempt - 1)))
        time.sleep(delay * (0.75 + random.random() * 0.5))

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def get_text(self, url: str, **kwargs: Any) -> str:
        return self.get(url, **kwargs).text

    def get_bytes(self, url: str, **kwargs: Any) -> bytes:
        return self.get(url, **kwargs).content

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.get(url, **kwargs).json()


_SHARED: HttpClient | None = None
_SHARED_LOCK = threading.Lock()


def shared_client() -> HttpClient:
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None:
            _SHARED = HttpClient()
        return _SHARED
