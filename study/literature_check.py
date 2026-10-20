"""Credential-free, non-LLM smoke check of bounded literature retrieval.

Run with ``python -m study.literature_check --query ... --url ... --output ...``.
The supplied URL is fetched independently even if search fails, so the saved
diagnostic distinguishes discovery failures from source accessibility failures.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from .literature import LiteratureClient


async def check_literature(query, url, *, timeout=15):
    """Return evidence for one search and one fetch, using unchanged client bounds."""
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "query": query,
              "url": url, "timeout_seconds": timeout, "model_calls": 0}
    client = LiteratureClient()
    try:
        for name, value in (("search", query), ("fetch", url)):
            try:
                evidence = await getattr(client, name)(value, timeout=timeout)
                if name == "search":
                    useful = any(isinstance(item, dict) and
                                 any(isinstance(item.get(key), str) and item[key].strip()
                                     for key in ("title", "doi", "url", "passage"))
                                 for item in evidence.get("results", []))
                    error = None if useful else "Search returned no useful results"
                else:
                    text = evidence.get("text")
                    useful = isinstance(text, str) and bool(text.strip())
                    error = None if useful else "Fetch returned no source passage"
                result[name] = {"ok": useful, "evidence": evidence, "error": error}
            except Exception as error:
                result[name] = {"ok": False, "error": f"{type(error).__name__}: {error}",
                                "evidence": getattr(error, "details", {})}
    finally:
        await client.aclose()
    result["ok"] = result["search"]["ok"] and result["fetch"]["ok"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=15,
                        help="Seconds per operation, between 0 and 15 (default: 15)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 15:
        parser.error("--timeout must be positive and at most 15 seconds")
    result = asyncio.run(check_literature(args.query, args.url, timeout=args.timeout))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f'Literature retrieval check: {"passed" if result["ok"] else "failed"}; evidence: {args.output}')
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
