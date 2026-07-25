"""Zusammenbau der konfigurierbaren Anwendung."""

from __future__ import annotations

from .config import Settings
from .llm import ConfigurationError, LLMService
from .output import render_output, write_output
from .ui import TerminalUI
from .workflow import CoachWorkflow


def main() -> None:
    """Der Einstieg verdrahtet Komponenten; fachliche Entscheidungen bleiben in den Modulen testbar."""
    settings = Settings.from_environment()
    ui = TerminalUI()
    ui.welcome(settings)

    service = LLMService(
        settings,
        on_retry=ui.show_notice,
        status_factory=ui.status,
    )

    try:
        service.validate()
    except ConfigurationError as exc:
        ui.show_notice(str(exc), error=True)
        raise SystemExit(1) from exc

    try:
        result = CoachWorkflow(settings, service, ui).run()
        write_output(settings.output_file, render_output(result))
    except KeyboardInterrupt:
        ui.console.print("\n[alert.red]Abgebrochen.[/alert.red]")
        raise SystemExit(130) from None
    except Exception as exc:
        ui.show_notice(f"Der Ablauf wurde wegen eines Fehlers beendet:\n{exc}", error=True)
        raise

    ui.show_notice(f"Ergebnis gespeichert: {settings.output_file.resolve()}")
    if result.final_review:
        closing = (
            "Fertig. Im Ergebnis stehen das validierte Profil, der optionale Abgleich und "
            "die final überarbeiteten Antworten. Prüfe vor der Verwendung noch einmal jede Aussage."
        )
    else:
        closing = (
            "Der erste Entwurf wurde gespeichert. Das automatische Abschlussreview blieb technisch "
            "ohne Textantwort und kann später erneut ausgeführt werden."
        )
    ui.coach_say(closing)
