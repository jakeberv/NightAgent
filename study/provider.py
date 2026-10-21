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
import copy
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


def completion_tools(tools):
    """Project our analysis schema into an API-compatible object envelope.

    Anthropic rejects root-level combinators. Advertise the bounded parameter
    alternatives inside `params`; the controller and worker still enforce the
    original model-specific conditional schema before any trial can execute.
    """
    projected = copy.deepcopy(tools)
    for tool in projected:
        function = tool.get("function", {})
        schema = function.get("parameters", {})
        if function.get("name") != "run_analysis" or "allOf" not in schema:
            continue
        alternatives = []
        for clause in schema.pop("allOf"):
            model = clause["if"]["properties"]["model"]["const"]
            restrictions = clause["then"]["properties"]
            if "params" not in restrictions:
                for field, constraint in restrictions.items():
                    if "const" not in constraint:
                        raise ValueError(f"Unsupported model constraint for {field}")
                    advertised = schema["properties"][field]
                    advertised["description"] = (advertised.get("description", "") +
                        f" For model={model}, {field} must be {constraint['const']!r}.").strip()
                continue
            parameters = restrictions["params"]
            parameters["description"] = f"Parameters for model={model}; use only with that model."
            alternatives.append(parameters)
        schema["properties"]["params"] = {
            "type": "object",
            "description": "Choose the parameter alternative matching the selected model. "
                           "Model/parameter consistency is checked locally.",
            "anyOf": alternatives,
        }
    return projected


class ProviderError(RuntimeError):
    """A failed call, including whatever accounting evidence was received."""

    def __init__(self, message: str, details: dict[str, Any]):
        super().__init__(message)
        self.details = details


def _reject_nonfinite_json(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_json_float(value):
    number = float(value)
    if not math.isfinite(number):
        _reject_nonfinite_json(value)
    return number


def _response_json(body):
    return json.loads(body, parse_float=_finite_json_float, parse_constant=_reject_nonfinite_json)


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
                        raw = self._redact(_response_json(body))
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
            payload["tools"] = completion_tools(tools)
        details = {"usage": None, "accounting_unknown": True,
                   "accounting_origin": "unknown",
                   "requested_model": self.model, "requested_provider": self.provider,
                   "request_tools": payload.get("tools", []),
                   "request_metadata": {}}
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        # Reconciliation is part of this attempt's caller budget, never extra time.
        reserve = min(5.0, timeout * .1)
        failure = None
        try:
            # One authoritative total deadline covers both the POST and receipt.
            async with asyncio.timeout_at(deadline):
                try:
                    async with asyncio.timeout_at(deadline - reserve):
                        message = await self._completion_response(payload, details, timeout)
                except (TimeoutError, httpx.HTTPError) as error:
                    details["error_type"] = type(error).__name__
                    failure = "Provider request timed out or failed in transport"
                except ProviderError as error:
                    failure = str(error)
                if details["accounting_unknown"]:
                    await self._reconcile(details, min(deadline, loop.time() + reserve))
                if failure:
                    raise ProviderError(failure, details)
                return {"message": message, **details}
        except asyncio.CancelledError as error:
            # Preserve cancellation, while the caller can journal received evidence.
            error.details = details
            raise
        except (TimeoutError, httpx.HTTPError) as error:
            details["error_type"] = type(error).__name__
            reconciliation = details.get("accounting_reconciliation")
            if reconciliation and reconciliation["status"] == "pending":
                reconciliation["status"] = "timeout"
            raise ProviderError("Provider request timed out or failed in transport", details) from None

    @staticmethod
    def _known_cost(usage):
        cost = usage.get("cost") if isinstance(usage, dict) else None
        try:
            return type(cost) in (int, float) and math.isfinite(cost) and cost >= 0
        except OverflowError:
            return False

    async def _completion_response(self, payload, details, timeout):
        # HTTP streaming retains headers before a slow body; the API remains
        # stream:false JSON. OpenRouter documents X-Generation-Id on all endpoints:
        # https://github.com/OpenRouterTeam/docs/blob/main/api_reference/streaming.mdx
        async with self._client.stream(
            "POST", "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload, timeout=timeout,
        ) as response:
            details["status_code"] = response.status_code
            details["request_metadata"] = self._redact({
                key: response.headers[key] for key in
                ("x-request-id", "request-id", "x-generation-id", "cf-ray")
                if key in response.headers
            })
            details["id"] = details["request_metadata"].get("x-generation-id")
            body = bytearray()
            try:
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
            except BaseException:
                details["response_text"] = self._redact(body[:4096].decode("utf-8", errors="replace"))
                raise
            try:
                raw = self._redact(_response_json(body))
            except (ValueError, UnicodeError):
                details["response_text"] = self._redact(body[:4096].decode("utf-8", errors="replace"))
                raise ProviderError("Provider returned invalid JSON", details) from None
            details["raw"] = raw
            if isinstance(raw, dict):
                details.update({key: raw.get(key) for key in ("provider", "model")})
                if raw.get("id") is not None:
                    if details["id"] is not None and details["id"] != raw["id"]:
                        details["generation_id_mismatch"] = True
                    else:
                        details["id"] = raw["id"]
                details["usage"] = raw.get("usage") if isinstance(raw.get("usage"), dict) else None
                details["accounting_unknown"] = not self._known_cost(details["usage"])
                if not details["accounting_unknown"]:
                    details["accounting_origin"] = "completion_usage"
            if not 200 <= response.status_code < 300 or not isinstance(raw, dict) or raw.get("error"):
                raise ProviderError("Provider request failed", details)
            try:
                message = raw["choices"][0]["message"]
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    raise ValueError
            except (KeyError, IndexError, TypeError, ValueError):
                raise ProviderError("Provider returned no assistant message", details) from None
            return message

    async def _reconcile(self, details, deadline):
        """Accept only a finalized receipt for this exact generation and model.

        https://openrouter.ai/docs/api/api-reference/generations/get-generation
        No key/balance aggregate, price estimate or failed-call zero is evidence.
        """
        generation_id = details.get("id")
        if not isinstance(generation_id, str) or not generation_id.strip():
            return
        evidence = details["accounting_reconciliation"] = {
            "source": "https://openrouter.ai/api/v1/generation",
            "generation_id": generation_id, "status": "pending",
        }
        if details.get("generation_id_mismatch"):
            evidence["status"] = "generation_id_mismatch"
            return
        try:
            async with asyncio.timeout_at(deadline):
                response = await self._client.get(evidence["source"], params={"id": generation_id},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=max(.001, deadline - asyncio.get_running_loop().time()))
                evidence["status_code"] = response.status_code
                # Keep malformed/nonstandard JSON as text, so NaN/Infinity cannot
                # leak into the durable journal's strict JSON accounting records.
                try:
                    raw = self._redact(_response_json(response.content))
                except (ValueError, UnicodeError):
                    evidence.update(status="invalid_json", response_text=self._redact(response.text[:4096]))
                    return
                evidence["raw"] = raw
                if not 200 <= response.status_code < 300:
                    evidence["status"] = "unavailable"
                    return
                data = raw.get("data") if isinstance(raw, dict) else None
                if not isinstance(data, dict) or raw.get("error"):
                    evidence["status"] = "invalid_receipt"
                    return
                if data.get("id") != generation_id or data.get("model") != self.model:
                    evidence["status"] = "receipt_mismatch"
                    return
                finish_reason = data.get("finish_reason")
                if not isinstance(finish_reason, str) or finish_reason not in {
                    "stop", "length", "tool_calls", "function_call", "content_filter", "error"
                }:
                    evidence["status"] = "not_final"
                    return
                usage = {"cost": data.get("total_cost"),
                         "prompt_tokens": data.get("native_tokens_prompt"),
                         "completion_tokens": data.get("native_tokens_completion")}
                token_fields = ("native_tokens_prompt", "native_tokens_completion",
                                "native_tokens_cached", "native_tokens_reasoning")
                if not self._known_cost(usage) or any(
                    type(data.get(key)) is not int or data[key] < 0 for key in token_fields
                    if key in token_fields[:2] or data.get(key) is not None
                ):
                    evidence["status"] = "invalid_accounting"
                    return
                for source, detail, target in (
                    ("native_tokens_cached", "prompt_tokens_details", "cached_tokens"),
                    ("native_tokens_reasoning", "completion_tokens_details", "reasoning_tokens"),
                ):
                    if data.get(source) is not None:
                        usage[detail] = {target: data[source]}
                details.update(usage=usage, accounting_unknown=False, accounting_origin="generation_receipt")
                evidence["status"] = "resolved"
        except TimeoutError:
            evidence["status"] = "timeout"
        except httpx.HTTPError as error:
            evidence.update(status="transport_failure", error_type=type(error).__name__)

    async def aclose(self):
        await self._client.aclose()
