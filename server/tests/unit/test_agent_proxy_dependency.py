from __future__ import annotations

import os

from app.api.deps import agent_service_client
from app.core.config import get_settings
from app.services.agent_proxy import OrchestratorAgentServiceClient, StubAgentServiceClient


def _reset_settings_cache() -> None:
    get_settings.cache_clear()


def test_agent_client_uses_stub_in_test_env() -> None:
    previous = os.environ.get("ENV")
    os.environ["ENV"] = "test"
    _reset_settings_cache()
    try:
        client = agent_service_client(get_settings())
        assert isinstance(client, StubAgentServiceClient)
    finally:
        if previous is None:
            os.environ.pop("ENV", None)
        else:
            os.environ["ENV"] = previous
        _reset_settings_cache()


def test_agent_client_uses_orchestrator_outside_test_env() -> None:
    previous = os.environ.get("ENV")
    os.environ["ENV"] = "development"
    _reset_settings_cache()
    try:
        client = agent_service_client(get_settings())
        assert isinstance(client, OrchestratorAgentServiceClient)
    finally:
        if previous is None:
            os.environ.pop("ENV", None)
        else:
            os.environ["ENV"] = previous
        _reset_settings_cache()
