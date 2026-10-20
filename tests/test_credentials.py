import pytest


@pytest.fixture(autouse=True)
def isolated_provider_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")


def test_tutorial_key_is_loaded_without_copying_or_overriding_other_settings(tmp_path, monkeypatch):
    from study.credentials import load_openrouter_env
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    source = tmp_path / ".env"
    source.write_text("LLM_API_KEY='fixture-secret' # comment\nLLM_BASE_URL=https://openrouter.ai/api/v1\n")
    before = source.read_bytes()
    load_openrouter_env(source)
    import os
    assert os.environ["OPENROUTER_API_KEY"] == "fixture-secret"
    assert "LLM_API_KEY" not in os.environ
    assert source.read_bytes() == before


def test_existing_environment_key_wins(tmp_path, monkeypatch):
    from study.credentials import load_openrouter_env
    monkeypatch.setenv("OPENROUTER_API_KEY", "existing")
    load_openrouter_env(tmp_path / "does-not-need-to-exist")
    import os
    assert os.environ["OPENROUTER_API_KEY"] == "existing"


@pytest.mark.parametrize("body", [
    "LLM_API_KEY=fixture-secret\nLLM_BASE_URL=https://other-provider.example/v1",
    "LLM_API_KEY=fixture-secret",
    'OPENROUTER_API_KEY="fixture-secret',
    "OPENROUTER_API_KEY=fixture-secret extra",
    "OPENROUTER_API_KEY=",
])
def test_bad_env_errors_never_echo_secret(tmp_path, monkeypatch, body):
    from study.credentials import load_openrouter_env
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    source = tmp_path / ".env"
    source.write_text(body)
    with pytest.raises(ValueError) as failed:
        load_openrouter_env(source)
    assert "fixture-secret" not in str(failed.value)


def test_env_shell_expressions_are_not_executed(tmp_path, monkeypatch):
    from study.credentials import load_openrouter_env
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    marker = tmp_path / "executed"
    source = tmp_path / ".env"
    source.write_text(f"OPENROUTER_API_KEY=$(touch {marker})")
    with pytest.raises(ValueError):
        load_openrouter_env(source)
    assert not marker.exists()


def test_explicit_openrouter_key_accepts_export_and_quotes(tmp_path, monkeypatch):
    from study.credentials import load_openrouter_env
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    source = tmp_path / ".env"
    source.write_text('export OPENROUTER_API_KEY="fixture-secret"\nUNRELATED=$(not-executed)')
    load_openrouter_env(source)
    import os
    assert os.environ["OPENROUTER_API_KEY"] == "fixture-secret"
