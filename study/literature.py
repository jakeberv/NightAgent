"""Bounded public literature evidence, without credentials or hidden retries.

Crossref search: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
Fetched text is untrusted evidence; it is never executed as instructions.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import math
import socket

import httpx


class LiteratureError(RuntimeError):
    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details or {}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "li", "jats:p"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li", "jats:p"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _text(value):
    parser = _Text()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _resolve(host, port):
    results = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(item[4][0] for item in results))


def _public(address):
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.is_global and not ip.is_multicast and not ip.is_unspecified and "%" not in address


class LiteratureClient:
    def __init__(self, *, max_bytes=262144, max_text=20000, max_results=5,
                 transport=None, resolver=None):
        if not 1 <= max_bytes <= 262144 or not 1 <= max_text <= 20000 or not 1 <= max_results <= 5:
            raise ValueError("Literature limits exceed the bounded maximum")
        self.max_bytes = max_bytes
        self.max_text = max_text
        self.max_results = max_results
        self._resolver = resolver or _resolve
        # Ignore proxy environment variables; a proxy would defeat IP pinning.
        # Do not reuse a checked IP connection for a different virtual host:
        # each HTTPS request must verify its own original TLS hostname.
        self._client = httpx.AsyncClient(transport=transport, trust_env=False,
                                        follow_redirects=False,
                                        limits=httpx.Limits(max_keepalive_connections=0))

    async def _read(self, original, *, timeout):
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        current = original
        redirects = []
        def evidence():
            return {"url": original, "final_url": current, "redirects": redirects}
        try:
            async with asyncio.timeout(timeout):
                visited = set()
                while True:
                    if not isinstance(current, str) or len(current) > 4096:
                        raise LiteratureError("Invalid public URL")
                    try:
                        url = httpx.URL(current).copy_with(fragment=None)
                    except httpx.InvalidURL:
                        raise LiteratureError("Invalid public URL") from None
                    if (url.scheme not in {"http", "https"} or not url.host or url.userinfo
                            or url.port not in {None, 80, 443} or "%" in url.host
                            or url.host.rstrip(".").lower() == "localhost"):
                        raise LiteratureError("Only public HTTP(S) URLs without credentials are allowed")
                    if str(url) in visited:
                        raise LiteratureError("Literature redirect loop")
                    visited.add(str(url))
                    try:
                        ipaddress.ip_address(url.host)
                    except ValueError:
                        addresses = await self._resolver(url.host, url.port or (443 if url.scheme == "https" else 80))
                    else:
                        addresses = [url.host]
                    if not addresses or any(not _public(address) for address in addresses):
                        raise LiteratureError("Destination is not exclusively public")
                    # Revalidate and pin every hop, preserving its virtual host
                    # and TLS name. Automatic redirects would bypass these checks.
                    pinned = url.copy_with(host=addresses[0])
                    host = url.netloc.decode("ascii")
                    async with self._client.stream(
                        "GET", pinned,
                        headers={"Host": host, "Accept-Encoding": "identity",
                                 "User-Agent": "NightAgent-study/1.0"},
                        extensions={"sni_hostname": url.host}, timeout=timeout,
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            if len(redirects) >= 5:
                                raise LiteratureError("Literature redirect limit exceeded")
                            location = response.headers.get("location")
                            if not location or len(location) > 4096:
                                raise LiteratureError("Invalid literature redirect location")
                            try:
                                # Relative locations resolve against the public
                                # URL, never the transport's pinned IP address.
                                current = str(url.join(location))
                            except httpx.InvalidURL:
                                raise LiteratureError("Invalid literature redirect location") from None
                            redirects.append({"url": str(url), "status": response.status_code,
                                              "location": current})
                            continue
                        if not 200 <= response.status_code < 300:
                            raise LiteratureError(f"Literature HTTP status {response.status_code}")
                        if response.headers.get("content-encoding", "identity").lower() != "identity":
                            raise LiteratureError("Compressed evidence is not accepted")
                        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                        if not (content_type.startswith("text/") or content_type in {"application/json", "application/xhtml+xml", "application/xml"}):
                            raise LiteratureError("Only text, HTML, XML or JSON evidence is supported")
                        data = bytearray()
                        truncated = False
                        # MockTransport may supply an already buffered response.
                        if response.is_stream_consumed:
                            data.extend(response.content[:self.max_bytes])
                            truncated = len(response.content) > self.max_bytes
                        else:
                            async for chunk in response.aiter_raw(chunk_size=4096):
                                remaining = self.max_bytes - len(data)
                                data.extend(chunk[:remaining])
                                if len(chunk) > remaining:
                                    truncated = True
                                    break
                        return bytes(data), content_type, truncated, str(url), redirects
        except LiteratureError as error:
            error.details = evidence()
            raise
        except (TimeoutError, httpx.HTTPError, OSError) as error:
            raise LiteratureError(f"Literature request failed: {type(error).__name__}",
                                  details=evidence()) from None

    async def search(self, query, *, timeout):
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise LiteratureError("Search query must contain 1–1000 characters")
        url = httpx.URL("https://api.crossref.org/works", params={
            "query.bibliographic": query, "rows": self.max_results,
            "select": "DOI,title,URL,abstract",
        })
        body, _, truncated, final_url, redirects = await self._read(str(url), timeout=timeout)
        if truncated:
            raise LiteratureError("Search response exceeds byte cap")
        try:
            items = json.loads(body)["message"]["items"]
            if not isinstance(items, list):
                raise ValueError
            results = []
            for item in items[:self.max_results]:
                results.append({"title": _text(" ".join(item.get("title", [])))[:1000],
                                "doi": str(item.get("DOI", ""))[:1000],
                                "url": str(item.get("URL", ""))[:4096],
                                "passage": _text(str(item.get("abstract", "")))[:2000]})
        except (ValueError, KeyError, TypeError, AttributeError):
            raise LiteratureError("Malformed Crossref search response") from None
        return {"source": "crossref", "query": query, "url": str(url),
                "final_url": final_url, "redirects": redirects,
                "retrieved_at": _now(), "results": results}

    async def fetch(self, url, *, timeout):
        body, content_type, truncated, final_url, redirects = await self._read(url, timeout=timeout)
        decoded = body.decode("utf-8", errors="replace")
        text = _text(decoded) if content_type in {"text/html", "application/xhtml+xml", "application/xml", "text/xml"} else " ".join(decoded.split())
        return {"url": url, "final_url": final_url, "redirects": redirects,
                "retrieved_at": _now(), "content_type": content_type,
                "text": text[:self.max_text], "bytes_read": len(body),
                "truncated": truncated or len(text) > self.max_text,
                "sha256": hashlib.sha256(body).hexdigest()}

    async def aclose(self):
        await self._client.aclose()
