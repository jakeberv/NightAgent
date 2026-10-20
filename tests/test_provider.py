"""Offline contract tests; HTTP transport doubles replace the paid boundary only."""
import asyncio
import json
import time

import httpx
import pytest

from study.provider import OpenRouter, ProviderError


def run(coro):
    return asyncio.run(coro)


def test_pins_provider_and_preserves_tool_reasoning_and_raw_accounting():
    seen = []
    message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "inspect_project", "arguments": "{}"}}], "reasoning_details": [{"type": "reasoning.encrypted", "data": "opaque", "signature": "sig"}]}
    raw = {"id": "gen-1", "model": "openai/gpt-4.1-mini", "provider": "Example", "choices": [{"message": message, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 11, "completion_tokens": 7, "cost": 0.002, "prompt_tokens_details": {"cached_tokens": 3}, "completion_tokens_details": {"reasoning_tokens": 4}}}
    async def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=raw, headers={"x-request-id": "req-1"})
    async def scenario():
        client = OpenRouter("openai/gpt-4.1-mini", "example", api_key="secret", transport=httpx.MockTransport(handler))
        messages = [{"role": "user", "content": "start"}, message, {"role": "tool", "tool_call_id": "call_1", "content": "{}"}]
        try:
            result = await client.complete(messages, [{"type": "function", "function": {"name": "inspect_project", "parameters": {"type": "object"}}}], timeout=1)
        finally:
            await client.aclose()
        assert result["message"] == message
        assert result["raw"] == raw
        assert result["usage"]["cost"] == 0.002
        assert result["request_metadata"]["x-request-id"] == "req-1"
        assert seen[0]["messages"] == messages
        assert seen[0]["provider"] == {"order": ["example"], "only": ["example"], "allow_fallbacks": False, "require_parameters": True}
        assert seen[0]["model"] == "openai/gpt-4.1-mini"
        assert seen[0]["temperature"] == 0
        assert seen[0]["max_tokens"] == 2048
        assert seen[0]["usage"] == {"include": True}
        assert seen[0]["tools"][0]["function"]["name"] == "inspect_project"
    run(scenario())


@pytest.mark.parametrize("response", [httpx.Response(429, json={"error": {"message": "unavailable secret"}}), httpx.Response(200, json={"id": "bad", "usage": {"cost": 0.1}, "choices": []}), httpx.Response(200, text="not json")])
def test_failure_is_not_retried_and_unknown_usage_is_not_zero(response):
    calls = []
    def handler(request):
        calls.append(request)
        return response
    async def scenario():
        client = OpenRouter("openai/gpt-4.1-mini", "example", api_key="secret", transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(ProviderError) as caught:
                await client.complete([], [], timeout=1)
            assert len(calls) == 1
            details = caught.value.details
            assert "secret" not in json.dumps(details)
            if response.status_code == 429:
                assert details["usage"] is None
                assert details["accounting_unknown"] is True
            if response.status_code == 200 and response.headers.get("content-type", "").startswith("application/json"):
                assert details["usage"] == {"cost": 0.1}
        finally:
            await client.aclose()
    run(scenario())


def test_total_deadline_bounds_slow_transport():
    calls = []
    async def handler(request):
        calls.append(request)
        await asyncio.sleep(1)
        return httpx.Response(200, json={})
    async def scenario():
        client = OpenRouter("openai/gpt-4.1-mini", "example", api_key="secret", transport=httpx.MockTransport(handler))
        started = time.monotonic()
        try:
            with pytest.raises(ProviderError) as caught:
                await client.complete([], [], timeout=0.02)
            assert caught.value.details["accounting_unknown"] is True
            assert time.monotonic() - started < 0.3
            assert len(calls) == 1
        finally:
            await client.aclose()
    run(scenario())


def test_missing_usage_stays_null():
    async def scenario():
        client = OpenRouter("openai/gpt-4.1-mini", "example", api_key="secret", transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "done"}}]})))
        try:
            assert (await client.complete([], [], timeout=1))["usage"] is None
        finally:
            await client.aclose()
    run(scenario())


@pytest.mark.parametrize("model,provider", [("", "example"), ("openai/gpt-4.1-mini", ""), ("openrouter/auto", "example")])
def test_requires_explicit_model_and_provider(model, provider):
    with pytest.raises(ValueError):
        OpenRouter(model, provider, api_key="secret")


@pytest.mark.parametrize("model", ["openrouter/free", "vendor/model:online"])
def test_rejects_automatic_model_or_builtin_browsing(model):
    with pytest.raises(ValueError):
        OpenRouter(model, "example", api_key="secret")


@pytest.mark.parametrize("model", ["perplexity/sonar", "perplexity/sonar-pro", "openai/gpt-4o-search-preview", "openai/gpt-4o-mini-search-preview", "unknown/plain-model", "anthropic/claude-sonnet-4.5:online", "openai/gpt-4.1:floor"])
def test_only_reviewed_plain_models_are_allowed_before_transport(model):
    def handler(request):
        pytest.fail("unreviewed model reached the network boundary")
    with pytest.raises(ValueError, match="reviewed plain model"):
        OpenRouter(model, "example", api_key="secret", transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("model", ["anthropic/claude-sonnet-4.5", "anthropic/claude-opus-4.1", "openai/gpt-4.1", "openai/gpt-4.1-mini", "google/gemini-2.5-pro"])
def test_reviewed_plain_models_reach_pinned_completion_boundary(model):
    async def scenario():
        def handler(request):
            assert json.loads(request.content)["model"] == model
            return httpx.Response(200, json={"model": model, "choices": [{"message": {"role": "assistant", "content": "done"}}], "usage": {"cost": 0}})
        client = OpenRouter(model, "example", api_key="secret", transport=httpx.MockTransport(handler))
        try:
            result = await client.complete([], [], timeout=1)
            assert result["model"] == model
            assert result["message"]["content"] == "done"
        finally:
            await client.aclose()
    run(scenario())


def test_describe_freezes_public_endpoint_prices_without_authorization():
    from datetime import datetime
    seen = []
    raw = {"data": {"id": "openai/gpt-4.1-mini", "name": "OpenAI: GPT-4.1 Mini", "endpoints": [{"name": "OpenAI | default", "provider_name": "OpenAI", "tag": "openai", "pricing": {"prompt": "0.0000004", "completion": "0.0000016", "input_cache_read": "0.0000001"}, "supported_parameters": ["tools", "temperature"]}]}}
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=raw)
    async def scenario():
        client = OpenRouter("openai/gpt-4.1-mini", "openai", api_key="secret", transport=httpx.MockTransport(handler))
        try:
            result = await client.describe(timeout=1)
            assert result["source"] == "https://openrouter.ai/api/v1/models/openai/gpt-4.1-mini/endpoints"
            assert result["model"] == "openai/gpt-4.1-mini"
            assert result["provider"] == "openai"
            assert result["endpoints"][0]["pricing"]["prompt"] == "0.0000004"
            assert result["pricing"][0]["pricing"]["input_cache_read"] == "0.0000001"
            assert result["raw"] == raw
            assert datetime.fromisoformat(result["timestamp"]).utcoffset().total_seconds() == 0
            assert seen[0].method == "GET"
            assert str(seen[0].url) == result["source"]
            assert "authorization" not in seen[0].headers
            assert len(seen) == 1
        finally:
            await client.aclose()
    run(scenario())


@pytest.mark.parametrize("response", [httpx.Response(429, json={"error": {"message": "secret unavailable"}}), httpx.Response(200, json={"data": {"endpoints": "bad"}}), httpx.Response(200, text="not JSON"), httpx.Response(200, content=b"x" * 1048577)])
def test_describe_rejects_failed_malformed_or_excessive_metadata_without_retry(response):
    calls = []
    def handler(request):
        calls.append(request)
        return response
    async def scenario():
        client = OpenRouter("openai/gpt-4.1-mini", "openai", api_key="secret", transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(ProviderError) as caught:
                await client.describe(timeout=1)
            assert "secret" not in json.dumps(caught.value.details)
            assert caught.value.details["operation"] == "describe"
            assert len(calls) == 1
        finally:
            await client.aclose()
    run(scenario())


def test_describe_has_total_deadline():
    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={})
    async def scenario():
        client = OpenRouter("openai/gpt-4.1-mini", "openai", api_key="secret", transport=httpx.MockTransport(handler))
        started = time.monotonic()
        try:
            with pytest.raises(ProviderError):
                await client.describe(timeout=.02)
            assert time.monotonic() - started < .3
        finally:
            await client.aclose()
    run(scenario())


@pytest.mark.parametrize("profile", ["magic", "regression", "legacy"])
def test_anthropic_receives_supported_analysis_schema_and_local_rules_stay_strict(profile):
    import copy
    from pathlib import Path
    import jsonschema
    from study.config import StudyConfig
    from study.controller import tools_for
    from study.problem import load_problem
    problem = None if profile == "legacy" else load_problem(
        Path(__file__).resolve().parents[1] / "study/problems" / f"{profile}.yaml")
    tools = tools_for("researcher", StudyConfig(), problem)
    original = copy.deepcopy(tools)
    local_schema = tools[2]["function"]["parameters"]
    valid = {"model": "ridge" if profile == "regression" else "logistic",
             "preprocessing": "standard", "params": {"alpha": 2} if profile == "regression" else {"C": 2}}
    from study.fake import scripted_contract
    valid["intent"] = scripted_contract("researcher", {})
    wrong_model_params = valid | {"params": {"n_estimators": 30}}
    async def handler(request):
        payload = json.loads(request.content)
        schema = payload["tools"][2]["function"]["parameters"]
        if set(schema) & {"allOf", "anyOf", "oneOf"}:
            return httpx.Response(400, json={"error": {
                "message": "input_schema does not support oneOf, allOf, or anyOf at the top level"}})
        jsonschema.validate(valid, schema)
        # The wire schema still exposes bounded, named parameters.
        for invalid in (valid | {"params": {"arbitrary_code": "run()"}},
                        valid | {"params": {"n_estimators": 999999}}):
            assert not jsonschema.Draft202012Validator(schema).is_valid(invalid)
        return httpx.Response(200, json={"choices": [{"message": {
            "role": "assistant", "tool_calls": [{"id": "fit", "type": "function",
            "function": {"name": "run_analysis", "arguments": json.dumps(valid)}}]}}],
            "usage": {"cost": 0}})
    async def scenario():
        client = OpenRouter("anthropic/claude-sonnet-4.5", "anthropic",
                            api_key="fixture", transport=httpx.MockTransport(handler))
        try:
            result = await client.complete([], tools, timeout=1)
            assert result["message"]["tool_calls"][0]["function"]["name"] == "run_analysis"
            assert "allOf" not in result["request_tools"][2]["function"]["parameters"]
        finally:
            await client.aclose()
    run(scenario())
    assert tools == original
    assert not jsonschema.Draft202012Validator(local_schema).is_valid(wrong_model_params)
