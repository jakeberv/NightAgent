"""Explicit, non-executing import of an OpenRouter key from a local env file."""
import os
from pathlib import Path
import shlex
from urllib.parse import urlsplit


def load_openrouter_env(path):
    """Import only the key; process settings take precedence over file settings."""
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        return
    values = {}
    for line in Path(path).read_text().splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        name = name.strip()
        if not separator or name not in {"OPENROUTER_API_KEY", "LLM_API_KEY", "LLM_BASE_URL"}:
            continue
        try:
            tokens = shlex.split(value, comments=True, posix=True)
        except ValueError:
            raise ValueError(f"Invalid quoting for {name} in env file") from None
        if len(tokens) != 1 or any(char in tokens[0] for char in ("$", "`", "\n", "\r")):
            raise ValueError(f"Expected a literal value for {name} in env file")
        values[name] = tokens[0]
    key = values.get("OPENROUTER_API_KEY")
    if not key and values.get("LLM_API_KEY"):
        try:
            url = urlsplit(values.get("LLM_BASE_URL", ""))
            valid = url.scheme == "https" and url.hostname == "openrouter.ai" and not url.username and not url.password
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("LLM_API_KEY requires an HTTPS OpenRouter LLM_BASE_URL in the env file")
        key = values["LLM_API_KEY"]
    if not key or not key.strip():
        raise ValueError("Env file has no nonempty OpenRouter API key")
    os.environ["OPENROUTER_API_KEY"] = key
