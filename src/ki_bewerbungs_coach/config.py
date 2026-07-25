"""Laden und Validieren der Laufzeitkonfiguration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    """Unveränderliche Einstellungen verhindern inkonsistente Providerzustände im Workflow."""

    model: str
    max_questions: int
    output_file: Path
    empty_retries: int
    retry_delay_seconds: float

    @classmethod
    def from_environment(cls, base_dir: Path | None = None) -> "Settings":
        """Lädt lokale Konfiguration, ohne bestehende Prozessvariablen unbeabsichtigt zu überschreiben."""
        load_local_environment(base_dir)
        return cls(
            model=os.getenv("MODEL", "claude-sonnet-4-6"),
            max_questions=max(1, _read_int("MAX_QUESTIONS", 12)),
            output_file=Path(os.getenv("OUTPUT_FILE", "bewerbung_output.md")),
            empty_retries=max(0, _read_int("LLM_EMPTY_RETRIES", 1)),
            retry_delay_seconds=max(0.0, _read_float("LLM_RETRY_DELAY_SECONDS", 1.0)),
        )


def load_local_environment(base_dir: Path | None = None) -> Path | None:
    """Sucht wenige vorhersehbare Orte, damit Secrets nicht über das Repository verteilt werden."""
    start = (base_dir or Path.cwd()).resolve()
    candidates = (start / ".env", start.parent / ".env")
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return candidate
    return None


def _read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} muss eine ganze Zahl sein, erhalten: {value!r}") from exc


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} muss eine Zahl sein, erhalten: {value!r}") from exc
