from __future__ import annotations

import gzip

import pytest
from check_urls import (
    Limits,
    Response,
    TransientURLError,
    URLPolicyError,
    check,
    clear_proxies,
    decode_body,
    public_address,
    redact,
)

PUBLIC = "8.8.8.8"


def resolver(host, port, type):
    return [(2, 1, 6, "", (PUBLIC, 0))]


class Fake:
    def __init__(self, responses, peer=PUBLIC):
        self.responses = list(responses)
        self.calls = []
        self.peer = peer

    def request(self, **kw):
        self.calls.append(kw)
        r = self.responses.pop(0)
        return Response(r[0], r[1], r[2], self.peer)


def test_proxy_canary_removed_and_redaction():
    env = {"HTTP_PROXY": "http://canary", "https_proxy": "http://canary"}
    clear_proxies(env)
    assert "HTTP_PROXY" not in env and env["NO_PROXY"] == "*"
    assert "abc" not in redact("token=abc")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.1.1",
        "100.64.0.1",
        "192.0.2.1",
        "198.18.0.1",
        "224.0.0.1",
        "0.0.0.0",
        "240.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "2001:db8::1",
        "ff00::1",
        "::",
        "::ffff:8.8.8.8",
    ],
)
def test_rejects_every_nonpublic_class(address):
    with pytest.raises(URLPolicyError):
        public_address(address)


def test_mixed_dns_fails_closed():
    def mixed(*a, **k):
        return [(2, 1, 6, "", (PUBLIC, 0)), (2, 1, 6, "", ("10.0.0.1", 0))]

    with pytest.raises(URLPolicyError):
        check("https://example.com", transport=Fake([(200, {}, b"ok")]), resolver=mixed)


def test_peer_mismatch_rebinding_fails():
    with pytest.raises(URLPolicyError):
        check(
            "https://example.com",
            transport=Fake([(200, {}, b"ok")], peer="1.1.1.1"),
            resolver=resolver,
        )


def test_redirect_revalidation_downgrade_and_hops():
    with pytest.raises(URLPolicyError):
        check(
            "https://example.com",
            transport=Fake([(302, {"location": "http://example.org"}, b"")]),
            resolver=resolver,
        )
    with pytest.raises(URLPolicyError):
        check(
            "https://example.com",
            transport=Fake([(302, {"location": "https://example.com"}, b"")] * 3),
            resolver=resolver,
            limits=Limits(max_hops=1),
        )


def test_statuses_and_limits_and_compression_bomb():
    for status, expected, blocking in [
        (401, "restricted", False),
        (403, "restricted", False),
        (404, "broken", True),
        (410, "broken", True),
        (429, "transient", True),
        (500, "transient", True),
    ]:
        out = check("https://example.com", transport=Fake([(status, {}, b"")]), resolver=resolver)
        assert (out["status"], out["blocking"]) == (expected, blocking)
    bomb = gzip.compress(b"x" * 10000)
    with pytest.raises(URLPolicyError):
        decode_body(bomb, "gzip", Limits(max_decompressed=100, max_ratio=2))


def test_chunked_oversize_and_timeout_propagate():
    with pytest.raises(URLPolicyError):
        check(
            "https://example.com",
            transport=Fake([(200, {}, b"x" * 11)]),
            resolver=resolver,
            limits=Limits(max_compressed=10),
        )

    class Timeout:
        def request(self, **kw):
            raise TransientURLError("timeout")

    with pytest.raises(TransientURLError):
        check("https://example.com", transport=Timeout(), resolver=resolver)
