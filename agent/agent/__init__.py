"""Compatibility package for ADK module loading.

ADK loads apps from inside the ``agent/`` directory. In that context imports like
``agent.app...`` resolve against a top-level ``agent`` package under the current
working directory, not the repository's ``agent/`` directory itself.

This shim makes ``agent.app`` point at the real ``app`` package so existing
absolute imports keep working in both direct Python execution and ``adk web``.
"""

from __future__ import annotations

import sys
from importlib import import_module

app_pkg = import_module("app")
sys.modules.setdefault(__name__ + ".app", app_pkg)

