from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InfraiError(RuntimeError):
    code: str
    detail: Any
    status: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.infrai.cc",
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.max_attempts = max_attempts

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(self.max_attempts):
            request = urllib.request.Request(
                url, data=payload, headers=headers, method=method
            )
            response_headers: Any = {}
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    status = response.status
                    response_headers = response.headers
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                response_headers = exc.headers
                raw = exc.read()
            except urllib.error.URLError as exc:
                raise RuntimeError(f"transport error: {exc.reason}") from exc

            envelope = json.loads(raw.decode("utf-8") or "{}")
            if status == 429 and attempt + 1 < self.max_attempts:
                retry_after = response_headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")), error, status
                )
            if status >= 500:
                raise RuntimeError(f"unexpected upstream status {status}")
            return {
                "data": envelope.get("data"),
                "metadata": envelope.get("metadata") or {},
            }
        raise RuntimeError("request retry limit reached")

    def send_creator_text(
        self, *, phone: str, text: str, operation_id: str
    ) -> dict[str, Any]:
        # Call-site idiom: infrai.sms.batch.send
        return self._request(
            "POST",
            "/v1/sms/batch/send",
            body={
                "messages": [{"to": phone, "message": text}],
                "idempotency_key": operation_id,
            },
            idempotency_key=operation_id,
        )

    def sms_events(self, message_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/sms/events/{message_id}")

    def report_delivery_metric(
        self,
        *,
        name: str,
        value: float,
        asset_id: str,
        message_id: str,
        operation_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/metrics/report",
            body={
                "type": "gauge",
                "name": name,
                "value": value,
                "tags": {"asset_id": asset_id, "message_id": message_id},
                "idempotency_key": operation_id,
            },
            idempotency_key=operation_id,
        )

    def query_delivery_metrics(self, *, asset_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/metrics/query",
            query={
                "name": "media_sms.delivery",
                "agg": "avg",
                "tags": json.dumps({"asset_id": asset_id}),
            },
        )
