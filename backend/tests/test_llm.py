from __future__ import annotations

import os

from app.core.config import settings
from app.services import llm


def test_resolve_model_prefers_configured(monkeypatch):
    monkeypatch.setattr(llm, "_available_models", lambda: {"llama3.2:3b", "llama3:latest"})
    monkeypatch.setattr(settings, "ollama_llm_model", "llama3.2:3b")
    assert llm.resolve_model() == "llama3.2:3b"


def test_resolve_model_falls_back_when_configured_missing(monkeypatch):
    monkeypatch.setattr(llm, "_available_models", lambda: {"llama3:latest"})
    monkeypatch.setattr(settings, "ollama_llm_model", "llama3.2:3b")
    assert llm.resolve_model() == "llama3:latest"


def test_resolve_model_returns_configured_when_ollama_unreachable(monkeypatch):
    monkeypatch.setattr(llm, "_available_models", lambda: set())
    monkeypatch.setattr(settings, "ollama_llm_model", "llama3.2:3b")
    assert llm.resolve_model() == "llama3.2:3b"


def test_get_llm_applies_threads_and_output_cap(monkeypatch):
    monkeypatch.setattr(llm, "resolve_model", lambda: "llama3.2:3b")
    model = llm.get_llm(num_predict=42)
    assert model.model == "llama3.2:3b"
    assert model.num_predict == 42
    assert model.num_thread == (os.cpu_count() or 4)
    assert model.num_ctx == settings.ollama_num_ctx


def test_complete_returns_friendly_message_when_ollama_down(monkeypatch):
    def boom(*args, **kwargs):
        raise ConnectionError("Connection refused to http://localhost:11434")

    monkeypatch.setattr(llm, "get_llm", boom)
    out = llm.complete("system prompt", "user prompt")
    assert "Ollama is currently not running" in out
