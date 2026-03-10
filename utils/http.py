from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LOGGER = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, calls_per_second: float = 1.0) -> None:
        self.min_interval = 1.0 / calls_per_second if calls_per_second > 0 else 0.0
        self._lock = Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()


def build_session(user_agent: str, extra_headers: dict[str, str] | None = None) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
    if extra_headers:
        session.headers.update(extra_headers)
    return session


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    limiter: RateLimiter | None = None,
    timeout: int = 30,
    **kwargs: Any,
) -> Any:
    if limiter:
        limiter.wait()
    try:
        response = session.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()
    except requests.RequestException as exc:
        LOGGER.warning("Request failed for %s: %s", url, exc)
        return None


def request_content(
    session: requests.Session,
    url: str,
    *,
    limiter: RateLimiter | None = None,
    timeout: int = 60,
    stream: bool = False,
    **kwargs: Any,
) -> requests.Response | None:
    if limiter:
        limiter.wait()
    try:
        response = session.get(url, timeout=timeout, stream=stream, **kwargs)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        LOGGER.warning("Content download failed for %s: %s", url, exc)
        return None


def request_text(
    session: requests.Session,
    method: str,
    url: str,
    *,
    limiter: RateLimiter | None = None,
    timeout: int = 30,
    **kwargs: Any,
) -> str | None:
    if limiter:
        limiter.wait()
    try:
        response = session.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        LOGGER.warning("Request failed for %s: %s", url, exc)
        return None
