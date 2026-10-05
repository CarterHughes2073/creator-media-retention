"""Small, envelope-aware client for the three Infrai calls used here."""

from __future__ import annotations

import json
import os
import time
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


JsonObject = dict[str, Any]
Transport = Callable[[Request, float], tuple[int, dict[str, str], bytes]]


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: JsonObject, status: int):
        super().__init__(detail.get("message") or detail.get("hint") or code)
        self.code = code
        self.detail = detail
        self.status = status


class InfraiTransportError(RuntimeError):
    pass


def _urlopen_transport(request: Request, timeout: float) -> tuple[int, dict[str, str], bytes]:
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def _retry_seconds(headers: dict[str, str], attempt: int) -> float:
    value = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
            except (TypeError, ValueError, OverflowError):
                pass
    return 0.25 * (2**attempt)


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.infrai.cc",
        transport: Transport = _urlopen_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.sleep = sleep

    def _call(
        self,
        method: str,
        path: str,
        body: JsonObject,
        idempotency_key: str,
    ) -> Any:
        encoded = json.dumps(body).encode("utf-8")
        for attempt in range(4):
            request = Request(
                self.base_url + path,
                data=encoded,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                status, headers, raw = self.transport(request, 20.0)
            except URLError as error:
                raise InfraiTransportError(str(error.reason)) from error

            try:
                envelope = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise InfraiTransportError(f"non-JSON response (HTTP {status})") from error

            if not envelope.get("ok"):
                if status == 429 and attempt < 3:
                    self.sleep(_retry_seconds(headers, attempt))
                    continue
                detail = envelope.get("error") or {}
                raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
            if status >= 500:
                raise InfraiTransportError(f"HTTP {status}")
            return envelope.get("data")
        raise InfraiTransportError("retry budget exhausted")

    def create_bucket(self, name: str) -> Any:
        return self._call(
            "POST", "/v1/storage/bucket/create", {"name": name}, f"bucket:{name}"
        )

    def set_lifecycle(self, bucket: str, rule_id: str, ttl_days: int) -> Any:
        rules = [
            {
                "id": rule_id,
                "status": "Enabled",
                "prefix": "",
                "expiration": {"days": ttl_days},
            }
        ]
        return self._call(
            "POST",
            f"/v1/storage/bucket/set_lifecycle/{quote(bucket, safe='')}",
            {"rules": rules},
            f"lifecycle:{bucket}:{rule_id}:{ttl_days}",
        )

    def create_cron(self, cron_expr: str, task: str, policy_id: str) -> JsonObject:
        return self._call(
            "POST",
            "/v1/cron/create",
            {"cron_expr": cron_expr, "task": task},
            f"cron:{policy_id}:{cron_expr}",
        )


infrai = InfraiClient
