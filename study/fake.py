"""Deterministic offline demonstration; never an experimental LLM result."""
import json


class FakeModel:
    def __init__(self):
        self.trials = 0

    async def complete(self, messages, tools, *, timeout):
        role = messages[0]["content"].splitlines()[0]
        calls = []
        content = "Compare nonlinear capacity against the completed validation evidence."
        if role == "ROLE: researcher":
            options = [
                {"model": "logistic", "preprocessing": "standard", "params": {"C": 1}},
                {"model": "random_forest", "preprocessing": "none", "params": {"n_estimators": 30}},
                {"model": "histogram_gradient_boosting", "preprocessing": "none", "params": {"max_iter": 40}},
                {"model": "histogram_gradient_boosting", "preprocessing": "standard", "params": {"max_iter": 80}},
            ]
            config = options[self.trials % len(options)]
            self.trials += 1
            calls = [{"id": f"fake-{self.trials}", "type": "function",
                      "function": {"name": "run_analysis", "arguments": json.dumps(config)}}]
        elif role == "ROLE: supervisor" and len(messages) == 2 and any(
                t["function"]["name"] == "literature_search" for t in tools):
            content = "Research question: do nonlinear tree models warrant a controlled comparison?"
            calls = [{"id": "fake-literature", "type": "function", "function": {
                "name": "literature_search", "arguments": json.dumps({"query": "gradient boosting classification"})}}]
        message = {"role": "assistant", "content": content}
        if calls:
            message["tool_calls"] = calls
        return {"message": message, "usage": {"prompt_tokens": 100, "completion_tokens": 30,
            "cost": 0, "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0}},
            "id": f"offline-{self.trials}-{len(messages)}", "model": "offline-script",
            "provider": "offline", "raw": {"offline": True}}

    async def aclose(self):
        pass


class FakeLiterature:
    async def search(self, query, *, timeout):
        return {"query": query, "offline": True, "sources": [], "note": "Offline fixture: no supporting source found."}

    async def fetch(self, url, *, timeout):
        return {"url": url, "offline": True, "text": "Offline fixture, not external evidence."}
