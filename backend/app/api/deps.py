"""Request-scoped access to the stores and configuration held on ``app.state``."""

from __future__ import annotations

from fastapi import Request

from ..ai import get_provider
from ..ai.base import AIProvider
from ..config import Settings
from ..storage import ProjectStore, SettingsStore


def store(request: Request) -> ProjectStore:
    return request.app.state.store


def settings_store(request: Request) -> SettingsStore:
    return request.app.state.settings_store


def config(request: Request) -> Settings:
    return request.app.state.config


def ai_provider(request: Request) -> AIProvider | None:
    override = getattr(request.app.state, "ai_provider_override", None)
    if override is not None:
        return override
    return get_provider(config(request), settings_store(request).load())
