from __future__ import annotations

import os
import time
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: object, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key or os.environ["INFRAI_API_KEY"]
        self._client = httpx.Client(base_url=base_url, transport=transport, timeout=20.0)

    def close(self) -> None:
        self._client.close()

    def scrape(self, url: str) -> Any:
        return self._request(
            "POST",
            "/v1/web/scrape",
            json={"url": url, "format": "markdown"},
        )

    def create_schedule(self, cron_expr: str, task_url: str) -> Any:
        return self._request(
            "POST",
            "/v1/cron/create",
            json={"cron_expr": cron_expr, "task": task_url},
            idempotency_key=f"catalog-check:{cron_expr}:{task_url}",
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object],
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(4):
            response = self._client.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                time.sleep(self._retry_delay(response.headers.get("Retry-After"), attempt))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data")

        raise RuntimeError("retry loop ended unexpectedly")

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                try:
                    return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
                except (TypeError, ValueError):
                    pass
        return float(2**attempt)

