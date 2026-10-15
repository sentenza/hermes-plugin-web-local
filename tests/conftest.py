"""Make the plugin module and a Hermes checkout importable.

Run with the Python of a Hermes install (``agent`` / ``tools`` importable), or point
``HERMES_AGENT_REPO`` at a hermes-agent checkout.
"""
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PLUGIN_ROOT)
_repo = os.environ.get("HERMES_AGENT_REPO")
if _repo:
    sys.path.insert(1, _repo)
