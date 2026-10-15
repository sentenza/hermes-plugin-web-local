"""Keep partial local results within the existing extraction time budget."""
import asyncio
import threading

import provider as local_mod


def test_fast_result_survives_multiple_unresponsive_urls(monkeypatch):
    release = threading.Event()
    started = []

    def extract_one(url, format):
        started.append(url)
        if url != "https://fast.example":
            release.wait(2)
        return {"url": url, "title": "", "content": "readable"}

    monkeypatch.setattr(local_mod, "_extract_one", extract_one)
    monkeypatch.setattr(local_mod, "_EXTRACT_TIMEOUT_SECS", 0.05)
    monkeypatch.setattr(local_mod, "_batch_budget_secs", lambda: 0.05)
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False)
    urls = ["https://fast.example"] + [f"https://slow{i}.example" for i in range(4)]

    async def scenario():
        try:
            # Extra scheduling margin here must not permit four serial waits.
            results = await asyncio.wait_for(local_mod.LocalWebSearchProvider().extract(urls), 0.15)
            assert [item["url"] for item in results] == urls
            assert results[0]["content"] == "readable"
            assert all(item.get("error") for item in results[1:])
            assert started == urls[:2]  # no new threads after budget exhaustion
        finally:
            release.set()

    asyncio.run(scenario())


def test_empty_and_fast_batches_keep_order(monkeypatch):
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False)
    monkeypatch.setattr(local_mod, "_extract_one", lambda url, format: {"url": url, "content": "ok"})

    async def scenario():
        provider = local_mod.LocalWebSearchProvider()
        assert await provider.extract([]) == []
        urls = ["https://a.example", "https://b.example"]
        assert await provider.extract(urls) == [{"url": url, "content": "ok"} for url in urls]

    asyncio.run(scenario())


def test_interrupt_between_urls_prevents_new_work(monkeypatch):
    interrupted = False

    def extract_one(url, format):
        nonlocal interrupted
        interrupted = True
        return {"url": url, "content": "ok"}

    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: interrupted)
    monkeypatch.setattr(local_mod, "_extract_one", extract_one)
    results = asyncio.run(local_mod.LocalWebSearchProvider().extract(["https://a.example", "https://b.example"]))
    assert results == [{"url": "https://a.example", "content": "ok"},
                       {"url": "https://b.example", "error": "Interrupted", "title": ""}]


def _timed_extract(delays, started):
    def extract_one(url, format):
        started.append(url)
        threading.Event().wait(delays[url])
        return {"url": url, "content": "readable"}
    return extract_one


def test_batch_budget_follows_caller_cap_not_per_url_timeout(monkeypatch):
    """Three normal pages fit the caller's cap even if together they exceed one URL's timeout."""
    urls = [f"https://page{i}.example" for i in range(3)]
    started = []
    monkeypatch.setattr(local_mod, "_extract_one", _timed_extract(dict.fromkeys(urls, 0.03), started))
    monkeypatch.setattr(local_mod, "_EXTRACT_TIMEOUT_SECS", 0.05)
    monkeypatch.setattr("tools.web_tools_extract._extract_timeout_seconds", lambda: 1.0)
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False)
    results = asyncio.run(local_mod.LocalWebSearchProvider().extract(urls))
    assert [item.get("content") for item in results] == ["readable"] * 3


def test_short_caller_cap_still_returns_completed_items(monkeypatch):
    """A cap below the per-URL timeout must not discard the fast result with the batch."""
    release = threading.Event()
    urls = ["https://fast.example", "https://slow.example", "https://late.example"]
    started = []

    def extract_one(url, format):
        started.append(url)
        if url != "https://fast.example":
            release.wait(2)
        return {"url": url, "content": "readable"}

    monkeypatch.setattr(local_mod, "_extract_one", extract_one)
    monkeypatch.setattr("tools.web_tools_extract._extract_timeout_seconds", lambda: 0.2)
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False)

    async def scenario():
        try:
            results = await asyncio.wait_for(local_mod.LocalWebSearchProvider().extract(urls), 0.2)
            assert results[0]["content"] == "readable"
            assert all("budget" in item["error"] for item in results[1:])
            assert started == urls[:2]
        finally:
            release.set()

    asyncio.run(scenario())


def test_uncapped_caller_keeps_per_url_timeout(monkeypatch):
    urls = ["https://slow.example", "https://next.example"]
    started = []
    monkeypatch.setattr(local_mod, "_extract_one", _timed_extract({urls[0]: 0.2, urls[1]: 0}, started))
    monkeypatch.setattr(local_mod, "_EXTRACT_TIMEOUT_SECS", 0.05)
    monkeypatch.setattr("tools.web_tools_extract._extract_timeout_seconds", lambda: 0)
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False)
    results = asyncio.run(local_mod.LocalWebSearchProvider().extract(urls))
    assert "timed out after" in results[0]["error"]
    assert results[1]["content"] == "readable"
