from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.core.config import settings


_AVAILABLE_MODELS: set[str] | None = None


def _available_models() -> set[str]:
    """List locally installed Ollama models (cached). Empty set if unreachable."""
    global _AVAILABLE_MODELS
    if _AVAILABLE_MODELS is None:
        try:
            url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            _AVAILABLE_MODELS = {m.get("name", "") for m in data.get("models", [])}
        except Exception:
            _AVAILABLE_MODELS = set()
    return _AVAILABLE_MODELS


# Preferred order when the configured model is missing locally.
_FALLBACK_MODELS = ["llama3.2:3b", "llama3.2", "llama3"]


def resolve_model() -> str:
    """Return the configured model, or the best available fallback so agents never
    hard-fail just because a model was not pulled."""
    configured = settings.ollama_llm_model
    models = _available_models()
    if not models:
        return configured
    if configured in models:
        return configured
    for name in models:
        if name.split(":")[0] == configured.split(":")[0]:
            return name
    for candidate in _FALLBACK_MODELS:
        if candidate in models:
            return candidate
        for name in models:
            if name.split(":")[0] == candidate.split(":")[0]:
                return name
    return configured


def get_llm(response_format: str | None = None, num_predict: int | None = None) -> ChatOllama:
    options: dict[str, Any] = {
        "model": resolve_model(),
        "base_url": settings.ollama_base_url,
        "temperature": 0.2,
        # Keep the model resident so back-to-back agent calls skip the load cost.
        "client_kwargs": {"timeout": 1800.0},
        "keep_alive": "30m",
        # Bound the context window and threads for faster CPU-only inference.
        "num_ctx": settings.ollama_num_ctx,
        "num_thread": settings.ollama_num_thread or (os.cpu_count() or 4),
    }
    if num_predict is not None:
        options["num_predict"] = num_predict
    if response_format is not None:
        options["format"] = response_format
    return ChatOllama(
        **options,
    )


_CONNECTION_INDICATORS = [
    "connect",
    "11434",
    "connection refused",
    "operation not permitted",
    "network is unreachable",
    "network is disabled",
    "errno 1",
    "errno 61",
    "timed out",
    "timeout",
]


def _is_connection_error(exc: Exception) -> bool:
    """Return True if *exc* looks like an Ollama-unreachable / network error."""
    err = str(exc).lower()
    return any(keyword in err for keyword in _CONNECTION_INDICATORS)


_OLLAMA_DOWN_MSG = (
    "⚠️ Ollama is currently not running or unreachable at http://localhost:11434.\n\n"
    "To resolve this, open your terminal and run:\n"
    "```bash\n"
    "ollama serve\n"
    "ollama pull llama3\n"
    "```"
)


def complete(system: str, user: str, num_predict: int | None = None) -> str:
    """Call the configured Ollama model.  Returns a friendly fallback when Ollama is unreachable."""
    try:
        llm = get_llm(num_predict=num_predict)
        message = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return (message.content or "").strip()
    except Exception as exc:
        if _is_connection_error(exc):
            return _OLLAMA_DOWN_MSG
        raise


def complete_json(system: str, user: str, num_predict: int | None = None) -> str:
    """Like complete() but requests JSON output format."""
    try:
        llm = get_llm(response_format="json", num_predict=num_predict)
        message = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return (message.content or "").strip()
    except Exception as exc:
        if _is_connection_error(exc):
            return '{"error": "Ollama is not running. Please start it using \'ollama serve\'"}'
        raise



def _escape_control_characters(text: str) -> str:
    escaped: list[str] = []
    in_string = False
    escaped_character = False
    for character in text:
        if character == '"' and not escaped_character:
            in_string = not in_string
        if in_string and ord(character) < 0x20:
            replacements = {"\n": r"\n", "\r": r"\r", "\t": r"\t"}
            escaped.append(replacements.get(character, f"\\u{ord(character):04x}"))
        else:
            escaped.append(character)
        escaped_character = character == "\\" and not escaped_character
        if character != "\\":
            escaped_character = False
    return "".join(escaped)


def parse_json(text: str) -> Any:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = stripped[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return json.loads(_escape_control_characters(candidate))
        start_l = stripped.find("[")
        end_l = stripped.rfind("]")
        if start_l != -1 and end_l != -1 and end_l > start_l:
            return json.loads(stripped[start_l : end_l + 1])
        raise
