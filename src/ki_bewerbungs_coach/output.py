"""Ergebnisdarstellung und sichere Dateiausgabe."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CoachResult:
    """Ein benanntes Ergebnisobjekt verhindert vertauschte Strings zwischen Workflowphasen."""

    profile: str
    gap_analysis: str
    draft: str
    final_review: str


def render_output(result: CoachResult) -> str:
    """Optionale Abschnitte werden zentral aufgebaut, damit CLI und spätere UIs dasselbe Format nutzen."""
    sections = [
        "# Ergebnis des KI Bewerbungs Coach",
        "",
        "> KI-gestützter Entwurf. Die inhaltliche Verantwortung und Freigabe liegen bei der Person.",
        "",
        "## Validiertes Arbeitsstil-Profil",
        "",
        result.profile,
        "",
    ]

    if result.gap_analysis:
        sections.extend(["## Abgleich mit Unterlagen", "", result.gap_analysis, ""])

    sections.extend(["## Antworten · erster Entwurf", "", result.draft, ""])

    if result.final_review:
        sections.extend(
            [
                "## Kritisches Review und finale Fassung",
                "",
                result.final_review,
                "",
            ]
        )
    else:
        sections.extend(
            [
                "> Hinweis: Das automatische Abschlussreview lieferte trotz Wiederholungsversuchen "
                "keine Textantwort. Der erste Entwurf wurde vollständig gespeichert.",
                "",
            ]
        )

    return "\n".join(sections)


def write_output(path: Path, content: str) -> None:
    """Atomisches Ersetzen schützt das letzte vollständige Ergebnis bei einem Schreibabbruch."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
