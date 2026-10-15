"""Malformed HTTP charset must not discard an otherwise readable body."""
import httpx
import pytest

import provider as local


def _client(monkeypatch, charset, body):
    monkeypatch.setattr(local, "is_safe_url", lambda url: True)
    monkeypatch.setattr(local, "check_website_access", lambda url: None)
    monkeypatch.setattr(local, "_make_client", lambda: httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"content-type": f"text/plain; charset={charset}"},
            content=body))))


def test_unknown_charset_preserves_utf8_text(monkeypatch):
    _client(monkeypatch, "no-such-charset", "Curaçao — café".encode("utf-8"))
    result = local._extract_one("https://article.example/text", None)
    assert "error" not in result
    assert result["content"] == "Curaçao — café"
    assert result["raw_content"] == result["content"]


@pytest.mark.parametrize("charset,body,expected", [
    ("iso-8859-1", b"caf\xe9", "café"),
    ("utf-8", b"bad\xffbyte", "bad\ufffdbyte"),
    ("no-such-charset", b"bad\xffbyte", "bad\ufffdbyte"),
])
def test_charset_valid_and_invalid_bytes(monkeypatch, charset, body, expected):
    _client(monkeypatch, charset, body)
    result = local._extract_one("https://article.example/text", None)
    assert "error" not in result
    assert result["content"] == expected
