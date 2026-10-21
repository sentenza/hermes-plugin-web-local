"""Diagnostics for a missing trafilatura: the plugin must say WHERE to install it."""
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
