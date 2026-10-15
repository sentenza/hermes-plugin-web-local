"""Local web extract plugin for Hermes.

Fetches pages directly from this machine with ``httpx`` and reduces them to
readable text with ``trafilatura`` (Apache-2.0). No API key. Extract-only:
pair it with any search provider (ddgs, searxng, ...).

Loaded either as a package (relative import works) or by file path (no parent
package, so fall back to the sibling module).
"""

from __future__ import annotations

try:
    from .provider import LocalWebSearchProvider
except ImportError:  # pragma: no cover - path-load fallback
    from provider import LocalWebSearchProvider  # type: ignore[no-redef]


def register(ctx) -> None:
    """Register the local extract provider with the plugin context."""
    ctx.register_web_search_provider(LocalWebSearchProvider())
