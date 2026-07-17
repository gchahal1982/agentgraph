"""Credential-free, fail-closed HTTP(S) evidence URL checker.

The transport pins an approved address, preserves TLS SNI/hostname validation, and
checks the connected peer. A custom transport is injectable for complete offline tests.
"""

from __future__ import annotations

import argparse
import gzip
import http.client
import ipaddress
import os
import re
import socket
import ssl
import time
import zlib
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from _common import read_json, write_json

PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
SECRET = re.compile(r"(?i)(authorization|token|key|secret|password)=?[^&\s]*")


class URLPolicyError(ValueError):
    pass


class TransientURLError(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    max_headers: int = 64 * 1024
    max_compressed: int = 2 * 1024 * 1024
    max_decompressed: int = 8 * 1024 * 1024
    max_ratio: float = 20.0
    max_hops: int = 5
    wall_seconds: float = 20.0
    read_seconds: float = 10.0


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes
    peer_ip: str


class Transport(Protocol):
    def request(
        self,
        *,
        scheme: str,
        hostname: str,
        port: int,
        pinned_ip: str,
        path: str,
        timeout: float,
        max_headers: int,
        max_body: int,
    ) -> Response: ...


def clear_proxies(environ: dict[str, str] | None = None) -> None:
    target = os.environ if environ is None else environ
    for name in PROXY_VARS:
        target.pop(name, None)
    target["NO_PROXY"] = "*"
    target["no_proxy"] = "*"


def redact(text: str) -> str:
    return SECRET.sub(lambda m: m.group(1) + "=<redacted>", text)


def public_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        raise URLPolicyError("IPv4-mapped IPv6 destinations are forbidden")
    # is_global rejects private, loopback, link-local, CGNAT, documentation,
    # benchmark, multicast, unspecified and reserved ranges in supported Python.
    if (
        not address.is_global
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        or address.is_loopback
        or address.is_link_local
        or address.is_private
    ):
        raise URLPolicyError(f"non-public destination forbidden: {address}")
    return address


def resolve_public(
    hostname: str, resolver: Callable[..., list[tuple]] = socket.getaddrinfo
) -> list[str]:
    try:
        answers = resolver(hostname, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise TransientURLError(f"DNS failure for {hostname}") from exc
    addresses = sorted({item[4][0] for item in answers})
    if not addresses:
        raise TransientURLError(f"no DNS addresses for {hostname}")
    for address in addresses:
        public_address(address)
    return addresses


class PinnedHTTPTransport:
    """Strict socket transport. It fails closed if peer verification is unavailable."""

    def request(
        self,
        *,
        scheme: str,
        hostname: str,
        port: int,
        pinned_ip: str,
        path: str,
        timeout: float,
        max_headers: int,
        max_body: int,
    ) -> Response:
        public_address(pinned_ip)
        family = socket.AF_INET6 if ":" in pinned_ip else socket.AF_INET
        raw = socket.socket(family, socket.SOCK_STREAM)
        raw.settimeout(timeout)
        try:
            raw.connect((pinned_ip, port))
            peer = raw.getpeername()[0]
            if ipaddress.ip_address(peer) != ipaddress.ip_address(pinned_ip):
                raise URLPolicyError("connected peer differs from pinned address")
            stream = raw
            if scheme == "https":
                stream = ssl.create_default_context().wrap_socket(raw, server_hostname=hostname)
            request = f"GET {path} HTTP/1.1\r\nHost: {hostname}\r\nUser-Agent: agentgraph-sota-url-check/1.0\r\nAccept-Encoding: gzip, deflate\r\nConnection: close\r\n\r\n".encode(
                "ascii"
            )
            stream.sendall(request)
            response = http.client.HTTPResponse(stream)
            response.begin()
            header_bytes = sum(len(k) + len(v) + 4 for k, v in response.getheaders())
            if header_bytes > max_headers:
                raise URLPolicyError("response headers exceed limit")
            body = response.read(max_body + 1)
            if len(body) > max_body:
                raise URLPolicyError("compressed response exceeds limit")
            return Response(
                response.status, {k.lower(): v for k, v in response.getheaders()}, body, peer
            )
        except TimeoutError as exc:
            raise TransientURLError("URL read/connect timeout") from exc
        finally:
            with suppress(OSError):
                raw.close()


def decode_body(body: bytes, encoding: str, limits: Limits) -> bytes:
    if len(body) > limits.max_compressed:
        raise URLPolicyError("compressed response exceeds limit")
    try:
        if encoding.lower() == "gzip":
            decoded = gzip.decompress(body)
        elif encoding.lower() == "deflate":
            decoded = zlib.decompress(body)
        elif encoding.lower() in ("", "identity"):
            decoded = body
        else:
            raise URLPolicyError(f"unsupported content encoding: {encoding}")
    except (OSError, zlib.error) as exc:
        raise URLPolicyError("invalid compressed response") from exc
    if len(decoded) > limits.max_decompressed:
        raise URLPolicyError("decompressed response exceeds limit")
    if body and len(decoded) / len(body) > limits.max_ratio:
        raise URLPolicyError("decompression ratio exceeds limit")
    return decoded


def check(
    url: str,
    *,
    transport: Transport | None = None,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    limits: Limits | None = None,
) -> dict[str, object]:
    clear_proxies()
    transport = transport or PinnedHTTPTransport()
    limits = limits or Limits()
    started = time.monotonic()
    chain = []
    current = url
    for _hop in range(limits.max_hops + 1):
        if time.monotonic() - started > limits.wall_seconds:
            raise TransientURLError("wall-time limit exceeded")
        parsed = urlsplit(current)
        if parsed.scheme not in {"http", "https"}:
            raise URLPolicyError("only declared HTTP(S) URLs are permitted")
        if parsed.username or parsed.password:
            raise URLPolicyError("embedded credentials are forbidden")
        if not parsed.hostname:
            raise URLPolicyError("URL hostname is required")
        addresses = resolve_public(parsed.hostname, resolver)
        pinned = addresses[0]
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        response = transport.request(
            scheme=parsed.scheme,
            hostname=parsed.hostname,
            port=port,
            pinned_ip=pinned,
            path=path,
            timeout=limits.read_seconds,
            max_headers=limits.max_headers,
            max_body=limits.max_compressed,
        )
        if ipaddress.ip_address(response.peer_ip) != ipaddress.ip_address(pinned):
            raise URLPolicyError("actual peer differs from pinned address")
        chain.append({"url": redact(current), "status": response.status, "pinned_ip": pinned})
        if response.status in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if not location:
                raise URLPolicyError("redirect has no Location header")
            target = urljoin(current, location)
            if parsed.scheme == "https" and urlsplit(target).scheme != "https":
                raise URLPolicyError("HTTPS redirect downgrade forbidden")
            current = target
            continue
        decode_body(response.body, response.headers.get("content-encoding", ""), limits)
        if response.status in {404, 410}:
            return {"status": "broken", "blocking": True, "chain": chain}
        if response.status in {401, 403}:
            return {"status": "restricted", "blocking": False, "chain": chain}
        if response.status == 429 or response.status >= 500:
            return {"status": "transient", "blocking": True, "chain": chain}
        if response.status >= 400:
            return {"status": "broken", "blocking": True, "chain": chain}
        return {"status": "ok", "blocking": False, "chain": chain}
    raise URLPolicyError("redirect hop limit exceeded")


def preserve_last_good(path: Path, result: dict[str, object]) -> dict[str, object]:
    if result["status"] == "ok":
        write_json(path, result)
        return result
    return {**result, "last_good": read_json(path) if path.exists() else None}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--last-good", type=Path)
    a = p.parse_args()
    try:
        result = check(a.url)
        result = preserve_last_good(a.last_good, result) if a.last_good else result
    except (URLPolicyError, TransientURLError) as exc:
        result = {"status": "blocked", "blocking": True, "error": redact(str(exc))}
    print(__import__("json").dumps(result, indent=2, sort_keys=True))
    return 1 if result.get("blocking") else 0


if __name__ == "__main__":
    raise SystemExit(main())
