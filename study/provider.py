"""One-attempt OpenRouter Chat Completions boundary with unestimated usage.

Routing contract: https://openrouter.ai/docs/guides/routing/provider-selection
Reasoning messages are retained intact for subsequent tool-result turns.

Live studies fail closed to REVIEWED_PLAIN_MODELS. To extend the registry,
manually review the exact official OpenRouter model page and provider API:
confirm it is a plain tool-capable completion model with no implicit retrieval,
browsing, router, alias or preset. Record the review date/source below, add an
offline acceptance test, and freeze that exact model/provider in the suite
manifest. A new model name or suffix is never implicitly trusted. Recheck the
catalog before a live pilot; describe() snapshots metadata without inference.
Account-level presets enabling retrieval must remain disabled.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import math
import os
from typing import Any

import httpx


# Reviewed 2026-10-20 against https://openrouter.ai/<exact model id>.
# These are the ordinary completion models, whose external operations require
# explicitly supplied tools. Search-specialized models and variants are absent.
REVIEWED_PLAIN_MODELS = frozenset({
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-opus-4.1",
    "openai/gpt-4.1",
    "openai/gpt-4.1-mini",
    "google/gemini-2.5-pro",
})


class ProviderError(RuntimeError):
    """A failed call, including whatever accounting evidence was received."""

    def __init__(self, message: str, details: dict[str, Any]):
        super().__init__(message)
        self.details = details


class OpenRouter:
    def __init__(self, model, provider, temperature=0, max_tokens=2048,
                 api_key=None, transport=None):
        if not isinstance(model, str) or model.strip() not in REVIEWED_PLAIN_MODELS:
            raise ValueError("A reviewed plain model from REVIEWED_PLAIN_MODELS is required")
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("An explicit provider is required")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        if not isinstance(temperature, (float, int)) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError("temperature must be between zero and two")
        self.model = model.strip()
        self.provider = provider.strip()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")
        if not self._api_key or not self._api_key.strip():
            raise ValueError("OPENROUTER_API_KEY is required")
        self._client = httpx.AsyncClient(transport=transport, follow_redirects=False,
                                        trust_env=False)

    def _redact(self, value):
        if isinstance(value, str):
            return value.replace(self._api_key, "[REDACTED]")
        if isinstance(value, dict):
            return {self._redact(k): self._redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value

    async def describe(self, timeout: float = 15) -> dict:
        """Snapshot public endpoint/pricing provenance before starting a run.

        GET /api/v1/models/{author}/{slug}/endpoints, documented at
        https://openrouter.ai/docs/api/api-reference/endpoints/list-all-endpoints-for-a-model
        Prices remain raw strings in their documented units. They are provenance,
        never an estimate or substitute for the actual completion usage.cost.
        Sends no API key; public metadata failures raise without an auth retry.
        """
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        source = f"https://openrouter.ai/api/v1/models/{self.model}/endpoints"
        details = {"operation": "describe", "source": source,
                   "requested_model": self.model, "requested_provider": self.provider}
        try:
            async with asyncio.timeout(timeout):
                async with self._client.stream(
                    "GET", source, headers={"Accept-Encoding": "identity"},
                    timeout=timeout,
                ) as response:
                    details["status_code"] = response.status_code
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise ProviderError("Compressed provider metadata is not accepted", details)
                    maximum = 1048576
                    if response.is_stream_consumed:
                        body = response.content
                        if len(body) > maximum:
                            raise ProviderError("Provider metadata exceeds 1 MiB cap", details)
                    else:
                        content = bytearray()
                        async for chunk in response.aiter_raw(chunk_size=4096):
                            if len(content) + len(chunk) > maximum:
                                raise ProviderError("Provider metadata exceeds 1 MiB cap", details)
                            content.extend(chunk)
                        body = bytes(content)
                    try:
                        raw = self._redact(json.loads(body))
                    except (ValueError, UnicodeError):
                        details["response_text"] = self._redact(body[:4096].decode("utf-8", errors="replace"))
                        raise ProviderError("Provider metadata is not valid JSON", details) from None
                    details["raw"] = raw
                    if not 200 <= response.status_code < 300 or not isinstance(raw, dict) or raw.get("error"):
                        raise ProviderError("Provider metadata request failed", details)
                    try:
                        data = raw["data"]
                        endpoints = data["endpoints"]
                        if data.get("id") != self.model or not isinstance(endpoints, list) or any(not isinstance(endpoint, dict) for endpoint in endpoints):
                            raise ValueError
                    except (KeyError, TypeError, AttributeError, ValueError):
                        raise ProviderError("Provider metadata has invalid model/endpoints", details) from None
                    return {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source": source, "model": self.model,
                        "provider": self.provider, "endpoints": endpoints,
                        "pricing": [{"provider_name": endpoint.get("provider_name"),
                                     "tag": endpoint.get("tag"),
                                     "pricing": endpoint.get("pricing")}
                                    for endpoint in endpoints],
                        "raw": raw,
                    }
        except (TimeoutError, httpx.HTTPError) as error:
            details["error_type"] = type(error).__name__
            raise ProviderError("Provider metadata request timed out or failed in transport", details) from None

    async def complete(self, messages, tools, *, timeout: float) -> dict:
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        payload = {
            "model": self.model, "messages": messages,
            "temperature": self.temperature, "max_tokens": self.max_tokens,
            "provider": {"order": [self.provider], "only": [self.provider],
                         "allow_fallbacks": False, "require_parameters": True},
            "usage": {"include": True}, "stream": False,
        }
        if tools:
            payload["tools"] = tools
        details = {"usage": None, "accounting_unknown": True,
                   "requested_model": self.model, "requested_provider": self.provider,
                   "request_metadata": {}}
        try:
            # The outer timer includes pool wait, upload, headers and full body.
            async with asyncio.timeout(timeout):
                response = await self._client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload, timeout=timeout,
                )
                details["status_code"] = response.status_code
                details["request_metadata"] = self._redact({
                    key: response.headers[key] for key in
                    ("x-request-id", "request-id", "x-generation-id", "cf-ray")
                    if key in response.headers
                })
                try:
                    raw = self._redact(response.json())
                except ValueError:
                    details["response_text"] = self._redact(response.text[:4096])
                    raise ProviderError("Provider returned invalid JSON", details) from None
                details["raw"] = raw
                if isinstance(raw, dict):
                    details.update({key: raw.get(key) for key in ("id", "provider", "model")})
                    details["usage"] = raw.get("usage") if isinstance(raw.get("usage"), dict) else None
                    usage = details["usage"]
                    details["accounting_unknown"] = usage is None or usage.get("cost") is None
                if not 200 <= response.status_code < 300 or not isinstance(raw, dict) or raw.get("error"):
                    raise ProviderError("Provider request failed", details)
                try:
                    message = raw["choices"][0]["message"]
                    if not isinstance(message, dict) or message.get("role") != "assistant":
                        raise ValueError
                except (KeyError, IndexError, TypeError, ValueError):
                    raise ProviderError("Provider returned no assistant message", details) from None
                return {"message": message, "usage": details["usage"],
                        "id": raw.get("id"), "provider": raw.get("provider"),
                        "model": raw.get("model"), "raw": raw,
                        "request_metadata": details["request_metadata"]}
        except (TimeoutError, httpx.HTTPError) as error:
            details["error_type"] = type(error).__name__
            raise ProviderError("Provider request timed out or failed in transport", details) from None

    async def aclose(self):
        await self._client.aclose()
