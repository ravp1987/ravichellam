"""Thin client for the Torii REST API (https://developers.toriihq.com).

Auth: Bearer token via TORII_API_KEY.
Base URL defaults to https://api.toriihq.com and can be overridden with
TORII_API_URL (matches the env vars used by the official torii-cli).
"""
from __future__ import annotations

import os
import time
from typing import Any, Iterator

import requests

DEFAULT_BASE_URL = "https://api.toriihq.com"
API_VERSION = "v1.0"


class ToriiError(RuntimeError):
    pass


class ToriiClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.environ.get("TORII_API_KEY")
        if not self.api_key:
            raise ToriiError(
                "Missing API key. Set the TORII_API_KEY environment variable "
                "(Settings > API in the Torii dashboard to generate one)."
            )
        self.base_url = (base_url or os.environ.get("TORII_API_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        return f"{self.base_url}/{API_VERSION}/{path}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET with retry on 429 (rate limit) and 5xx."""
        url = self._url(path)
        backoff = 1.0
        for attempt in range(6):
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", backoff))
                time.sleep(wait)
                backoff = min(backoff * 2, 30)
                continue
            if resp.status_code >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            if resp.status_code == 404:
                return None
            if not resp.ok:
                raise ToriiError(f"GET {url} failed: {resp.status_code} {resp.text[:500]}")
            if not resp.content:
                return None
            return resp.json()
        raise ToriiError(f"GET {url} failed after retries")

    def get_all_pages(self, path: str, params: dict[str, Any] | None = None, page_size: int = 100) -> Iterator[dict]:
        """Yield items across paginated list endpoints.

        Torii's list endpoints return either a bare array or an object like
        {"data": [...], "pagination": {...}}. Handles both shapes and stops
        once a page returns fewer than page_size items or no data.
        """
        params = dict(params or {})
        offset = 0
        while True:
            page_params = dict(params, limit=page_size, offset=offset)
            payload = self.get(path, params=page_params)
            if payload is None:
                return
            items = payload["data"] if isinstance(payload, dict) and "data" in payload else payload
            if not items:
                return
            for item in items:
                yield item
            if len(items) < page_size:
                return
            offset += page_size

    def fields(self, resource: str) -> list[str] | None:
        """Discover available field names for a resource, e.g. 'apps', 'contracts'.

        Torii exposes /{resource}/fields on several resources. Returns None if
        the resource has no such endpoint.
        """
        payload = self.get(f"{resource}/fields")
        if payload is None:
            return None
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if isinstance(payload, list):
            return [f["name"] if isinstance(f, dict) and "name" in f else f for f in payload]
        return None

    def org(self) -> dict | None:
        return self.get("orgs/my")
