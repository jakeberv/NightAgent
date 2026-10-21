"""Offline regressions for one bounded paid attempt and its accounting receipt."""
import asyncio
from copy import deepcopy
import json
import time

import httpx
import pytest

from study.config import StudyConfig
from study.events import Journal, atomic_json
from study.model_calls import ModelCalls
from study.problem import legacy_problem
from study.provider import OpenRouter, ProviderError
from study.records import load_events
from study.run_state import RunState, StopRun


MODEL = "openai/gpt-4.1-mini"
SECRET = "fixture-private-key"


class DelayedBody(httpx.AsyncByteStream):
    def __init__(self, *, delay=1, failure=None, started=None):
        self.delay, self.failure, self.started = delay, failure, started
        self.closed = False

    async def __aiter__(self):
        yield ('{"debug":"' + SECRET + '",').encode()
        if self.started is not None:
            self.started.set()
        if self.failure is not None:
            raise self.failure
        await asyncio.sleep(self.delay)
        yield b'"choices":[]}'

    async def aclose(self):
        self.closed = True


def receipt(**changes):
    return {"data": {"id": "gen-fixture", "model": MODEL, "finish_reason": "stop",
        "native_tokens_prompt": 11, "native_tokens_completion": 7,
        "native_tokens_cached": 3, "native_tokens_reasoning": 2,
        "total_cost": .012, **changes}}


def completion(*, usage=None, generation_id="gen-fixture"):
    return {"id": generation_id, "model": MODEL,
        "choices": [{"message": {"role": "assistant", "content": "accepted"},
                     "finish_reason": "stop"}], "usage": usage}


def client_for(handler):
    return OpenRouter(MODEL, "example", api_key=SECRET, transport=httpx.MockTransport(handler))


def test_slow_body_preserves_header_and_resolves_charge_within_same_deadline():
    requests = []
    body = DelayedBody()

    async def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=receipt(debug=SECRET))
        assert json.loads(request.content)["stream"] is False
        return httpx.Response(200, headers={"x-generation-id": "gen-fixture",
            "x-request-id": "request-" + SECRET}, stream=body)

    async def scenario():
        client = client_for(handler)
        started = time.monotonic()
        try:
            with pytest.raises(ProviderError) as caught:
                await client.complete([], [], timeout=.15)
            details = caught.value.details
            assert details["id"] == "gen-fixture"
            assert details["request_metadata"]["x-generation-id"] == "gen-fixture"
            assert details["usage"] == {"cost": .012, "prompt_tokens": 11,
                "completion_tokens": 7, "prompt_tokens_details": {"cached_tokens": 3},
                "completion_tokens_details": {"reasoning_tokens": 2}}
            assert details["accounting_unknown"] is False
            assert details["accounting_origin"] == "generation_receipt"
            assert details["accounting_reconciliation"]["raw"]["data"]["debug"] == "[REDACTED]"
            assert SECRET not in json.dumps(details)
            assert "[REDACTED]" in details["response_text"]
            assert time.monotonic() - started < .3
            assert body.closed
            assert [request.method for request in requests] == ["POST", "GET"]
            assert str(requests[1].url) == "https://openrouter.ai/api/v1/generation?id=gen-fixture"
        finally:
            await client.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", [httpx.ReadError("body disconnected"), None])
def test_transport_or_missing_usage_reconciles_known_generation(failure):
    async def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=receipt())
        if failure is not None:
            return httpx.Response(200, headers={"x-generation-id": "gen-fixture"},
                                  stream=DelayedBody(failure=failure))
        return httpx.Response(200, json=completion())

    async def scenario():
        client = client_for(handler)
        try:
            if failure is not None:
                with pytest.raises(ProviderError) as caught:
                    await client.complete([], [], timeout=1)
                result = caught.value.details
            else:
                result = await client.complete([], [], timeout=1)
            assert result["usage"]["cost"] == .012
            assert result["accounting_origin"] == "generation_receipt"
            assert result["accounting_reconciliation"]["raw"] == receipt()
        finally:
            await client.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize("status,data", [
    (404, {"error": {"message": "not ready"}}),
    (200, receipt(id="gen-another")),
    (200, receipt(model="openai/gpt-4.1")),
    (200, receipt(finish_reason=None)),
    (200, receipt(finish_reason="in_progress")),
    (200, receipt(finish_reason=["stop"])),
    (200, receipt(finish_reason={})),
    (200, {"data": []}),
    (200, {"data": None}),
    (200, []),
    (200, None),
    (200, receipt(total_cost=None)),
    (200, receipt(total_cost=-.01)),
    (200, receipt(total_cost=True)),
    (200, receipt(total_cost="0.012")),
    (200, receipt(total_cost=float("nan"))),
    (200, receipt(total_cost=float("inf"))),
    (200, receipt(total_cost=10 ** 1000)),
    (200, receipt(native_tokens_prompt=True)),
    (200, receipt(native_tokens_completion=1.5)),
    (200, receipt(native_tokens_cached=-1)),
    (200, receipt(native_tokens_reasoning="2")),
])
def test_unavailable_mismatched_provisional_or_malformed_receipt_stays_unknown(status, data):
    methods = []

    async def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json=completion())
        # Bytes allow non-finite JSON without relying on httpx's strict encoder.
        return httpx.Response(status, content=json.dumps(data).encode())

    async def scenario():
        client = client_for(handler)
        try:
            result = await client.complete([], [], timeout=1)
            assert result["usage"] is None
            assert result["accounting_unknown"] is True
            assert result["accounting_origin"] == "unknown"
            assert result["accounting_reconciliation"]["status"] != "resolved"
            assert methods == ["POST", "GET"]
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_missing_optional_token_counts_are_not_invented():
    async def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json=completion())
        raw = receipt()
        del raw["data"]["native_tokens_cached"]
        raw["data"]["native_tokens_reasoning"] = None
        return httpx.Response(200, json=raw)

    async def scenario():
        client = client_for(handler)
        try:
            result = await client.complete([], [], timeout=1)
            assert result["usage"] == {"cost": .012, "prompt_tokens": 11, "completion_tokens": 7}
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_no_generation_id_does_not_guess_a_charge_or_lookup():
    methods = []

    async def handler(request):
        methods.append(request.method)
        return httpx.Response(200, json=completion(generation_id=None))

    async def scenario():
        client = client_for(handler)
        try:
            result = await client.complete([], [], timeout=1)
            assert result["usage"] is None
            assert result["accounting_unknown"] is True
            assert result["accounting_origin"] == "unknown"
            assert methods == ["POST"]
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_reconciliation_has_small_bounded_window_inside_total_deadline():
    methods = []

    async def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, headers={"x-generation-id": "gen-fixture"},
                                  stream=DelayedBody())
        await asyncio.sleep(1)
        return httpx.Response(200, json=receipt())

    async def scenario():
        client = client_for(handler)
        started = time.monotonic()
        try:
            with pytest.raises(ProviderError) as caught:
                await client.complete([], [], timeout=.15)
            details = caught.value.details
            assert details["request_metadata"]["x-generation-id"] == "gen-fixture"
            assert details["usage"] is None and details["accounting_unknown"] is True
            assert details["accounting_reconciliation"]["status"] == "timeout"
            assert time.monotonic() - started < .3
            assert methods == ["POST", "GET"]
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_early_missing_usage_does_not_spend_entire_timeout_on_receipt():
    async def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json=completion())
        await asyncio.sleep(1)
        return httpx.Response(200, json=receipt())

    async def scenario():
        client = client_for(handler)
        started = time.monotonic()
        try:
            result = await client.complete([], [], timeout=.5)
            assert time.monotonic() - started < .25
            assert result["usage"] is None
            assert result["accounting_reconciliation"]["status"] == "timeout"
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_mismatched_body_and_header_ids_cannot_reconcile_another_charge():
    methods = []

    async def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json=completion(generation_id="gen-wrong"),
                                  headers={"x-generation-id": "gen-fixture"})
        return httpx.Response(200, json=receipt())

    async def scenario():
        client = client_for(handler)
        try:
            result = await client.complete([], [], timeout=1)
            assert result["usage"] is None and result["accounting_unknown"] is True
            assert result["accounting_reconciliation"]["status"] == "generation_id_mismatch"
            assert result["raw"]["id"] == "gen-wrong"
            assert methods == ["POST"]
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_nonfinite_completion_evidence_can_be_written_to_strict_json_journal():
    async def handler(request):
        return httpx.Response(200, content=json.dumps(completion(
            generation_id=None, usage={"cost": float("nan")})).encode())

    async def scenario():
        client = client_for(handler)
        try:
            with pytest.raises(ProviderError) as caught:
                await client.complete([], [], timeout=1)
            assert caught.value.details["usage"] is None
            assert "NaN" in caught.value.details["response_text"]
            json.dumps(caught.value.details, allow_nan=False)
        finally:
            await client.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["completion", "generation_receipt"])
@pytest.mark.parametrize("exponent", ["1e400", "-1e400"])
def test_overflowing_json_exponents_preserve_failed_call_in_real_journal(tmp_path, operation, exponent):
    methods = []

    async def handler(request):
        methods.append(request.method)
        if operation == "completion":
            raw = completion(generation_id=None, usage={"cost": "OVERFLOW"})
            raw["debug"] = SECRET
        elif request.method == "POST":
            return httpx.Response(502, json={"id": "gen-fixture",
                "error": {"message": "upstream failure", "debug": SECRET}})
        else:
            raw = receipt(total_cost="OVERFLOW", debug=SECRET)
        body = json.dumps(raw).replace('"OVERFLOW"', exponent).encode()
        return httpx.Response(200, content=body)

    async def scenario():
        client = client_for(handler)
        state = RunState(StudyConfig(allowance_seconds=2, model_start_buffer_seconds=0),
                         legacy_problem(), clock=time.monotonic)
        journal = Journal(tmp_path, state.started)
        calls = ModelCalls(state=state, journal=journal, model=client,
                           context=lambda *args, **kwargs: "{}")
        try:
            with pytest.raises(StopRun, match="unknown_cost"):
                await calls("researcher", [{}, {}], [])
            events = load_events(tmp_path / "events.jsonl", policy="strict")
            assert [event["type"] for event in events] == ["model_call_started", "model_call"]
            failed = events[-1]
            assert failed["status"] == "failed" and failed["error"] == "ProviderError"
            assert failed["usage"] is None
            assert failed["accounting"]["calls"] == 1
            assert failed["accounting"]["cost_complete"] is False
            evidence = failed["details"]
            if operation == "generation_receipt":
                evidence = evidence["accounting_reconciliation"]
                assert evidence["status"] == "invalid_json"
            assert exponent in evidence["response_text"]
            assert "[REDACTED]" in evidence["response_text"]
            assert SECRET not in (tmp_path / "events.jsonl").read_text()
            assert methods == (["POST"] if operation == "completion" else ["POST", "GET"])
        finally:
            await client.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize("number", ["1e400", "-1e400", "NaN", "Infinity", "-Infinity"])
def test_describe_rejects_nonfinite_json_with_persistable_redacted_evidence(tmp_path, number):
    raw = {"data": {"id": MODEL, "endpoints": [{"tag": "example",
        "pricing": {"prompt": "NONFINITE"}}], "debug": SECRET}}
    body = json.dumps(raw).replace('"NONFINITE"', number).encode()

    async def scenario():
        client = client_for(lambda request: httpx.Response(200, content=body))
        try:
            with pytest.raises(ProviderError) as caught:
                await client.describe(timeout=1)
            details = caught.value.details
            assert number in details["response_text"]
            assert SECRET not in json.dumps(details)
            atomic_json(tmp_path / "provider-error.json", details)
            assert "[REDACTED]" in (tmp_path / "provider-error.json").read_text()
        finally:
            await client.aclose()
    asyncio.run(scenario())


class RecordingJournal:
    def __init__(self):
        self.events = []

    def emit(self, event_type, **payload):
        self.events.append(deepcopy({"type": event_type, **payload}))


def calls_for(model, **settings):
    state = RunState(StudyConfig(allowance_seconds=2, model_start_buffer_seconds=0,
        model_timeout_seconds=.15, **settings), legacy_problem(), clock=time.monotonic)
    journal = RecordingJournal()
    calls = ModelCalls(state=state, journal=journal, model=model,
                       context=lambda *args, **kwargs: "{}")
    return calls, state, journal


def test_billed_failed_attempt_is_accounted_once_then_retried():
    post_count = 0

    async def handler(request):
        nonlocal post_count
        if request.method == "GET":
            return httpx.Response(200, json=receipt())
        post_count += 1
        if post_count == 1:
            return httpx.Response(200, headers={"x-generation-id": "gen-fixture"},
                                  stream=DelayedBody())
        return httpx.Response(200, json=completion(usage={"cost": .003,
            "prompt_tokens": 2, "completion_tokens": 1}, generation_id="gen-retry"))

    async def scenario():
        client = client_for(handler)
        calls, state, journal = calls_for(client)
        try:
            result = await calls("researcher", [{}, {}], [])
            assert result["content"] == "accepted"
            assert state.accounting.calls == 2
            assert state.accounting.known_cost == pytest.approx(.015)
            assert state.accounting.cost_complete is True
            assert state.accounting.input_tokens == 13 and state.accounting.output_tokens == 8
            events = [event for event in journal.events if event["type"] == "model_call"]
            assert [event["status"] for event in events] == ["failed", "completed"]
            assert events[0]["details"]["accounting_origin"] == "generation_receipt"
            assert post_count == 2
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_external_cancellation_preserves_header_without_reconciliation_or_retry():
    async def scenario():
        started = asyncio.Event()
        body = DelayedBody(started=started)
        methods = []

        async def handler(request):
            methods.append(request.method)
            return httpx.Response(200, headers={"x-generation-id": "gen-fixture"}, stream=body)

        client = client_for(handler)
        calls, state, journal = calls_for(client)
        try:
            task = asyncio.create_task(calls("researcher", [{}, {}], []))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert state.accounting.calls == 1 and not state.accounting.cost_complete
            assert journal.events[-1]["status"] == "cancelled"
            assert journal.events[-1]["details"]["request_metadata"]["x-generation-id"] == "gen-fixture"
            assert SECRET not in json.dumps(journal.events)
            assert body.closed
            assert methods == ["POST"]
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_custom_adapter_without_timeout_support_remains_bounded():
    class CustomModel:
        async def complete(self, messages, tools, *, timeout):
            await asyncio.sleep(1)

    calls, state, journal = calls_for(CustomModel())
    started = time.monotonic()
    with pytest.raises(StopRun, match="unknown_cost"):
        asyncio.run(calls("researcher", [{}, {}], []))
    assert time.monotonic() - started < .3
    assert state.accounting.calls == 1 and journal.events[-1]["status"] == "failed"


@pytest.mark.parametrize("allow_unknown", [False, True])
def test_unresolved_failed_attempt_never_spends_retry_budget(allow_unknown):
    methods = []

    async def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(502, json={"id": "gen-fixture", "error": {"message": SECRET}})
        return httpx.Response(404, json={"error": {"message": "not ready"}})

    async def scenario():
        client = client_for(handler)
        calls, state, journal = calls_for(client, allow_unknown_cost=allow_unknown)
        try:
            with pytest.raises(StopRun, match="unknown_cost"):
                await calls("researcher", [{}, {}], [])
            assert methods == ["POST", "GET"]
            assert state.accounting.calls == 1 and not state.accounting.cost_complete
            assert SECRET not in json.dumps(journal.events)
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_known_failed_charge_still_obeys_dollar_cap_before_retry():
    methods = []

    async def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(502, json={"id": "gen-fixture", "error": {"message": "failed"}})
        return httpx.Response(200, json=receipt())

    async def scenario():
        client = client_for(handler)
        calls, state, _ = calls_for(client, dollar_cap=.01)
        try:
            with pytest.raises(StopRun, match="dollar_cap"):
                await calls("researcher", [{}, {}], [])
            assert methods == ["POST", "GET"]
            assert state.accounting.calls == 1
            assert state.accounting.known_cost == .012 and state.accounting.cost_complete
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_caller_keeps_provider_evidence_when_receipt_exhausts_total_deadline():
    async def handler(request):
        if request.method == "POST":
            return httpx.Response(200, headers={"x-generation-id": "gen-fixture"},
                                  stream=DelayedBody())
        await asyncio.sleep(1)
        return httpx.Response(200, json=receipt())

    async def scenario():
        client = client_for(handler)
        calls, state, journal = calls_for(client)
        try:
            with pytest.raises(StopRun, match="unknown_cost"):
                await calls("researcher", [{}, {}], [])
            event = journal.events[-1]
            assert event["error"] == "ProviderError"
            assert event["details"]["request_metadata"]["x-generation-id"] == "gen-fixture"
            assert event["details"]["accounting_reconciliation"]["status"] == "timeout"
            assert state.accounting.calls == 1 and not state.accounting.cost_complete
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_accounted_retry_is_skipped_when_remaining_time_fails_admission():
    clock = [100.]
    methods = []

    async def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(502, json={"id": "gen-fixture", "error": {"message": "failed"}})
        clock[0] += 9.5
        return httpx.Response(200, json=receipt())

    async def scenario():
        client = client_for(handler)
        state = RunState(StudyConfig(allowance_seconds=10, model_start_buffer_seconds=1),
                         legacy_problem(), clock=lambda: clock[0])
        journal = RecordingJournal()
        calls = ModelCalls(state=state, journal=journal, model=client,
                           context=lambda *args, **kwargs: "{}")
        try:
            with pytest.raises(StopRun, match="deadline") as caught:
                await calls("researcher", [{}, {}], [])
            assert caught.value.details["reason"] == "deadline_admission"
            assert methods == ["POST", "GET"]
            assert state.accounting.calls == 1 and state.accounting.cost_complete
            assert journal.events[-1]["type"] == "model_call_skipped"
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_overriding_subclass_does_not_inherit_trusted_deadline_capability():
    class CustomOpenRouter(OpenRouter):
        async def complete(self, messages, tools, *, timeout):
            await asyncio.sleep(1)

    async def scenario():
        client = CustomOpenRouter(MODEL, "example", api_key=SECRET)
        calls, state, _ = calls_for(client)
        started = time.monotonic()
        try:
            with pytest.raises(StopRun, match="unknown_cost"):
                await calls("researcher", [{}, {}], [])
            assert time.monotonic() - started < .3
            assert state.accounting.calls == 1
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_admission_stop_carries_specific_reason_without_charging():
    state = RunState(StudyConfig(allowance_seconds=.1, model_start_buffer_seconds=1),
                     legacy_problem(), clock=time.monotonic)
    journal = RecordingJournal()
    calls = ModelCalls(state=state, journal=journal, model=None, context=None)
    with pytest.raises(StopRun, match="deadline") as caught:
        asyncio.run(calls("supervisor", [{}, {}], []))
    assert caught.value.details["reason"] == "deadline_admission"
    assert caught.value.details["role"] == "supervisor"
    assert state.accounting.calls == 0
