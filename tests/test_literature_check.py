"""Retrieval smoke checks must work without a model and retain failed evidence."""
import json

import httpx
import pytest

from study.literature import LiteratureClient


def client_for(search_items, body="A useful source passage.", status=200):
    async def resolve(host, port):
        return ["93.184.216.34"]
    def respond(request):
        if request.headers["host"] == "api.crossref.org":
            return httpx.Response(200, json={"message": {"items": search_items}})
        return httpx.Response(status, text=body, headers={"content-type": "text/plain"})
    return LiteratureClient(transport=httpx.MockTransport(respond), resolver=resolve)


def test_cli_writes_real_retrieval_evidence_without_provider_credentials(tmp_path, monkeypatch):
    from study import literature_check
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(literature_check, "LiteratureClient", lambda: client_for([
        {"title": ["Paper"], "DOI": "10.1/paper", "URL": "https://example.org/paper"}]))
    output = tmp_path / "nested" / "check.json"
    assert literature_check.main(["--query", "classification", "--url", "https://example.org/paper",
                                  "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["ok"] is True and result["model_calls"] == 0
    assert result["search"]["evidence"]["results"][0]["title"] == "Paper"
    assert result["fetch"]["evidence"]["text"] == "A useful source passage."
    assert len(result["fetch"]["evidence"]["sha256"]) == 64


@pytest.mark.parametrize("items,body,status,failed_stage", [
    ([], "Passage", 200, "search"),
    ([{}], "Passage", 200, "search"),
    ([{"title": ["Paper"], "URL": "https://example.org"}], "  ", 200, "fetch"),
    ([{"title": ["Paper"], "URL": "https://example.org"}], "Blocked", 403, "fetch"),
])
def test_cli_returns_nonzero_for_empty_or_failed_retrieval(tmp_path, monkeypatch, items, body, status, failed_stage):
    from study import literature_check
    monkeypatch.setattr(literature_check, "LiteratureClient", lambda: client_for(items, body, status))
    output = tmp_path / "check.json"
    code = literature_check.main(["--query", "classification", "--url", "https://example.org/paper",
                                  "--output", str(output)])
    result = json.loads(output.read_text())
    assert code == 1 and result["ok"] is False
    assert result[failed_stage]["ok"] is False
    assert result[failed_stage]["error"]
    assert "search" in result and "fetch" in result


def test_check_preserves_private_address_protection(tmp_path, monkeypatch):
    from study import literature_check
    monkeypatch.setattr(literature_check, "LiteratureClient", lambda: client_for([
        {"title": ["Paper"], "URL": "https://example.org"}]))
    output = tmp_path / "check.json"
    code = literature_check.main(["--query", "classification", "--url", "http://127.0.0.1/",
                                  "--output", str(output)])
    result = json.loads(output.read_text())
    assert code == 1
    assert "public" in result["fetch"]["error"]
    assert result["fetch"]["evidence"]["url"] == "http://127.0.0.1/"
