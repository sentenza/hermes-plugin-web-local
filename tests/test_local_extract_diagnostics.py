"""Diagnostics for a missing trafilatura: the plugin must say WHERE to install it."""
import asyncio

import pytest

import provider


def test_dependency_problem_none_when_installed():
    assert provider._dependency_problem() is None


def test_dependency_problem_names_interpreter_and_remedy(monkeypatch):
    monkeypatch.setattr(provider, "_find_spec", lambda name: None)

    problem = provider._dependency_problem()

    assert "trafilatura" in problem
    assert provider.sys.executable in problem      # which python is broken
    assert "uv pip install" in problem             # what to run


def test_is_available_false_when_module_missing(monkeypatch):
    monkeypatch.setattr(provider, "_find_spec", lambda name: None)
    assert provider.LocalWebSearchProvider().is_available() is False


def test_is_available_true_when_module_present(monkeypatch):
    monkeypatch.setattr(provider, "_find_spec", lambda name: object())
    assert provider.LocalWebSearchProvider().is_available() is True


def test_extract_short_circuits_without_network(monkeypatch):
    monkeypatch.setattr(provider, "_find_spec", lambda name: None)

    def _boom():
        raise AssertionError("no HTTP client may be built when the dependency is missing")

    monkeypatch.setattr(provider, "_make_client", _boom)

    results = asyncio.run(
        provider.LocalWebSearchProvider().extract(["https://example.com/a", "https://example.com/b"])
    )

    assert len(results) == 2
    for item in results:
        assert item["url"].startswith("https://example.com/")
        assert item["content"] == ""
        assert "trafilatura" in item["error"]
        assert provider.sys.executable in item["error"]
