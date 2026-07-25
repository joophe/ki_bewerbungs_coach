"""Provideranbindung und Normalisierung von Modellantworten."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from .config import Settings

try:
    import anthropic
except ImportError:  # pragma: no cover - wird über validate() verständlich gemeldet
    anthropic = None

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

RetryCallback = Callable[[str], None]
StatusFactory = Callable[[str], Any]


class ConfigurationError(RuntimeError):
    """Kennzeichnet lokale Konfigurationsfehler getrennt von Providerfehlern."""


class EmptyModelResponse(RuntimeError):
    """Erlaubt dem Workflow einen gezielten Fallback statt eines vollständigen Abbruchs."""


class LLMService:
    """Kapselt Providerunterschiede, ohne vollständige Austauschbarkeit vorzutäuschen."""

    def __init__(
        self,
        settings: Settings,
        *,
        on_retry: RetryCallback | None = None,
        status_factory: StatusFactory | None = None,
    ) -> None:
        self.settings = settings
        self.on_retry = on_retry
        self.status_factory = status_factory
        self._client: Any | None = None
        self._model_name: str | None = None

    def validate(self) -> None:
        """Fehlende Pakete und Secrets werden vor dem ersten Interviewschritt sichtbar gemacht."""
        model = self.settings.model
        required: dict[str, str] = {}

        if model.startswith("claude"):
            if anthropic is None:
                raise ConfigurationError("Python-Paket 'anthropic' fehlt.")
            required["ANTHROPIC_API_KEY"] = "Anthropic Console → API Keys"
        elif model.startswith("gemini/"):
            self._require_openai_package()
            required["GEMINI_API_KEY"] = "Google AI Studio → API Key"
        elif model.startswith("azure/"):
            self._require_openai_package()
            required["AZURE_OPENAI_API_KEY"] = "Azure Portal → OpenAI Resource → Keys"
            required["AZURE_OPENAI_ENDPOINT"] = "Azure Portal → OpenAI Resource → Endpoint"
        elif not model.startswith("ollama/"):
            self._require_openai_package()
            required["OPENAI_API_KEY"] = "OpenAI Platform → API Keys"

        missing = [key for key in required if not os.getenv(key)]
        if missing:
            details = "\n".join(f"• {key}: {required[key]}" for key in missing)
            raise ConfigurationError(
                "Folgende Konfiguration fehlt:\n\n"
                f"{details}\n\n"
                "Die Werte können in einer .env-Datei hinterlegt werden."
            )

    def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        user_input: str | None = None,
    ) -> str:
        """Leere Providerantworten werden begrenzt wiederholt, ohne den Gesprächsverlauf zu verändern."""
        if user_input is not None:
            messages.append({"role": "user", "content": user_input})

        last_diagnostic = "keine Provider-Diagnose verfügbar"
        attempts = self.settings.empty_retries + 1

        for attempt in range(attempts):
            payload_messages = list(messages)
            if attempt > 0:
                payload_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Der vorherige Aufruf enthielt keine sichtbare Textantwort. "
                            "Bitte bearbeite die ursprüngliche Aufgabe vollständig und gib "
                            "ausschließlich normalen Text beziehungsweise Markdown aus."
                        ),
                    }
                )

            if self.status_factory:
                with self.status_factory("Der KI Bewerbungs Coach denkt nach …"):
                    answer, last_diagnostic = self._request(system, payload_messages)
            else:
                answer, last_diagnostic = self._request(system, payload_messages)

            if answer:
                messages.append({"role": "assistant", "content": answer})
                return answer

            if attempt < attempts - 1:
                if self.on_retry:
                    self.on_retry(
                        "Das Modell hat keine sichtbare Textantwort geliefert. "
                        "Der Aufruf wird automatisch wiederholt.\n"
                        f"Technische Diagnose: {last_diagnostic}"
                    )
                if self.settings.retry_delay_seconds:
                    time.sleep(self.settings.retry_delay_seconds)

        raise EmptyModelResponse(
            "Das Modell hat auch nach den automatischen Wiederholungsversuchen keine "
            f"sichtbare Textantwort geliefert. Technische Diagnose: {last_diagnostic}"
        )

    def _request(self, system: str, messages: list[dict[str, str]]) -> tuple[str, str]:
        if self.settings.model.startswith("claude"):
            return self._request_anthropic(system, messages)
        return self._request_openai_compatible(system, messages)

    def _request_anthropic(
        self,
        system: str,
        messages: list[dict[str, str]],
    ) -> tuple[str, str]:
        assert anthropic is not None
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        payload = messages or [{"role": "user", "content": "Bitte beginne."}]
        response = self._client.messages.create(
            model=self.settings.model,
            max_tokens=4096,
            system=system,
            messages=payload,
        )
        answer = extract_anthropic_text(response.content)
        diagnostic = f"stop_reason={getattr(response, 'stop_reason', None)!r}"
        return answer, diagnostic

    def _request_openai_compatible(
        self,
        system: str,
        messages: list[dict[str, str]],
    ) -> tuple[str, str]:
        client, model_name = self._openai_client()
        payload = [{"role": "system", "content": system}] + (
            messages or [{"role": "user", "content": "Bitte beginne."}]
        )
        response = client.chat.completions.create(model=model_name, messages=payload)
        choice = response.choices[0]
        answer = extract_openai_text(choice.message)
        diagnostic = (
            f"finish_reason={getattr(choice, 'finish_reason', None)!r}, "
            f"refusal={getattr(choice.message, 'refusal', None)!r}"
        )
        return answer, diagnostic

    def _openai_client(self) -> tuple[Any, str]:
        if self._client is not None and self._model_name is not None:
            return self._client, self._model_name

        self._require_openai_package()
        model = self.settings.model

        if model.startswith("ollama/"):
            base_url = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1")
            self._client = OpenAI(base_url=base_url, api_key="ollama")
            self._model_name = model.split("/", 1)[1]
        elif model.startswith("gemini/"):
            self._client = OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=os.getenv("GEMINI_API_KEY"),
            )
            self._model_name = model.split("/", 1)[1]
        elif model.startswith("azure/"):
            from openai import AzureOpenAI

            self._client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            )
            self._model_name = model.split("/", 1)[1]
        else:
            self._client = OpenAI(
                base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
                api_key=os.getenv("OPENAI_API_KEY"),
            )
            self._model_name = model

        return self._client, self._model_name

    @staticmethod
    def _require_openai_package() -> None:
        if OpenAI is None:
            raise ConfigurationError("Python-Paket 'openai' fehlt.")


def extract_openai_text(message: Any) -> str:
    """Normalisiert String- und Part-Responses verbreiteter OpenAI-kompatibler Gateways."""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
            else:
                text = getattr(item, "text", None) or getattr(item, "content", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()

    return ""


def extract_anthropic_text(content: Any) -> str:
    """Mehrere Textblöcke werden verbunden, weil SDK-Antworten nicht auf einen Block begrenzt sind."""
    if not isinstance(content, list):
        return ""
    return "".join(
        block.text
        for block in content
        if getattr(block, "type", "") == "text" and isinstance(getattr(block, "text", None), str)
    ).strip()
