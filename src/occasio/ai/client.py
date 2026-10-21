"""Thin wrapper around the Anthropic SDK.

* Disabled (returns ``None``) when there is no key or ``OCCASIO_AI_ENABLED=false``.
* 20 s timeout per request; the SDK retries transient errors (429/5xx/connection) up to 2x.
* ``max_tokens`` is capped per task and oversized prompts are refused (cost guard).
* Responses are constrained with JSON-schema structured output, then parsed.
* A bounded in-memory LRU cache keyed by a hash of (model, task, prompts) avoids
  paying twice for the same request.
* Never raises for API problems: callers fall back to template output on ``None``.
  Logs carry the task name and outcome only, never user content.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Any

import anthropic

from occasio.config import Settings

log = logging.getLogger("occasio.ai")

TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 2
MAX_PROMPT_CHARS = 12_000
MAX_TOKENS = {"ideas": 1200, "intake": 500, "explain": 900}
CACHE_SIZE = 256


class AIClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        enabled: bool = True,
        sdk: Any = None,  # injected in tests; defaults to anthropic.Anthropic
        cache_size: int = CACHE_SIZE,
    ) -> None:
        self.model = model
        self.enabled = enabled and bool(api_key or sdk)
        self._api_key = api_key
        self._sdk: Any = sdk
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._cache_size = cache_size
        self._lock = Lock()

    @classmethod
    def from_settings(cls, settings: Settings) -> AIClient:
        return cls(
            api_key=settings.anthropic_api_key, model=settings.model, enabled=settings.ai_enabled
        )

    def _client(self) -> Any:
        if self._sdk is None:
            self._sdk = anthropic.Anthropic(
                api_key=self._api_key, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES
            )
        return self._sdk

    def complete_json(
        self, task: str, *, system: str, user: str, schema: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run one structured-output request. Returns parsed JSON or ``None`` on any failure."""
        if not self.enabled:
            return None
        if len(system) + len(user) > MAX_PROMPT_CHARS:
            log.warning("ai.%s refused: prompt too large", task)
            return None
        key = hashlib.sha256(
            json.dumps([self.model, task, system, user], ensure_ascii=False).encode()
        ).hexdigest()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                log.info("ai.%s cache hit", task)
                return self._cache[key]

        started = time.monotonic()
        try:
            response = self._client().messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS.get(task, 500),
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
                timeout=TIMEOUT_SECONDS,
            )
        except anthropic.APIError as exc:
            log.warning("ai.%s failed: %s", task, type(exc).__name__)
            return None

        elapsed = time.monotonic() - started
        stop = getattr(response, "stop_reason", None)
        if stop not in (None, "end_turn"):
            log.warning("ai.%s unusable stop_reason=%s", task, stop)
            return None
        text = "".join(
            getattr(block, "text", "")
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text"
        )
        try:
            data = json.loads(text)
        except ValueError:
            log.warning("ai.%s returned non-JSON", task)
            return None
        if not isinstance(data, dict):
            log.warning("ai.%s returned non-object JSON", task)
            return None

        log.info("ai.%s ok in %.2fs", task, elapsed)
        with self._lock:
            self._cache[key] = data
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return data
