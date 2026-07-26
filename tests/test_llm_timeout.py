from pathlib import Path

import httpx
import openai
import pytest

from ki_bewerbungs_coach.config import Settings
from ki_bewerbungs_coach.llm import EmptyModelResponse, LLMService, TIMEOUT_ERROR_TYPES


def _settings(**overrides: object) -> Settings:
    base = dict(
        model="some-openai-model",
        max_questions=1,
        output_file=Path("out.md"),
        empty_retries=0,
        retry_delay_seconds=0.0,
        timeout_seconds=1.0,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_openai_timeout_types_are_collected() -> None:
    assert openai.APITimeoutError in TIMEOUT_ERROR_TYPES


def test_timeout_is_converted_to_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    service = LLMService(_settings())

    def boom(system: str, messages: list) -> tuple[str, str]:
        raise openai.APITimeoutError(request=httpx.Request("POST", "http://example"))

    monkeypatch.setattr(service, "_request", boom)

    # Statt endlos zu blockieren, wird das Timeout zu einer leeren Antwort und
    # löst nach Ausschöpfen der Retries einen sauberen Fehler (Fallback) aus.
    with pytest.raises(EmptyModelResponse):
        service.complete("system", [])
