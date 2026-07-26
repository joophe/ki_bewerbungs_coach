"""Terminaldarstellung und Nutzereingaben."""

from __future__ import annotations

import sys
from contextlib import AbstractContextManager

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from .config import Settings

# Farben sind für einen dunklen Terminalhintergrund abgestimmt (Web-Demo & übliche Terminals).
BRAND_BLUE = "#5B9BFF"
ACCENT_GOLD = "#F4B400"
ALERT_RED = "#FF6B6B"
TEXT_INK = "#E5E7EB"
TEXT_MUTED = "#9CA3AF"

THEME = Theme(
    {
        "brand.blue": f"bold {BRAND_BLUE}",
        "brand.gold": f"bold {ACCENT_GOLD}",
        "alert.red": f"bold {ALERT_RED}",
        "text.ink": TEXT_INK,
        "muted": f"dim {TEXT_MUTED}",
        "question": f"bold {BRAND_BLUE}",
        "answer": "bold",
    }
)

PHASES = (
    "Kontext",
    "Reflexionsinterview",
    "Profilentwurf",
    "Eigene Korrektur",
    "Abgleich mit Unterlagen",
    "Finale Antworten",
)

# Die Web-Demo liefert einen Monospace-Font (DejaVu Sans Mono) mit, der diese
# Glyphen exakt einzellig enthält – dadurch bleibt die Rahmen-Box browser-
# unabhängig sauber ausgerichtet. Im lokalen Terminal hängt die Darstellung vom
# installierten Font ab (die meisten gängigen Monospace-Fonts enthalten sie).
FACES = {
    "friendly": "◕‿◕",
    "curious": "◔‿◔",
    "thinking": "◑‿◑",
    "critical": "◕◠◕",
}


class TerminalUI:
    """Eine konsistente Oberfläche trennt Coach-Dialog, Dokumente und Systemzustände."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(theme=THEME, highlight=False)

    def _avatar(self, face: str) -> Text:
        """Ein gemeinsamer Renderer verhindert, dass Startansicht und Dialog optisch auseinanderlaufen."""
        return Text.from_markup(
            f"[brand.blue]╭───╮\n│{FACES.get(face, FACES['friendly'])}│\n╰─┬─╯[/brand.blue]"
        )

    def welcome(self, settings: Settings) -> None:
        """Der Nutzen steht vor technischen Details, weil zuerst Vertrauen in den Ablauf nötig ist."""
        avatar = self._avatar('friendly')
        title = Text("KI Bewerbungs Coach", style="brand.blue")
        tagline = Text(
            "Von konkreten Erfahrungen zu einer authentischen Bewerbung.",
            style="brand.gold",
        )
        description = Text(
            "In sechs Schritten reflektieren wir deine Arbeitsweise, gleichen sie mit "
            "der Zielrolle ab und entwickeln daraus einen Bewerbungstext, den du selbst "
            "prüfen und freigeben kannst.",
            style="text.ink",
        )

        body = Table.grid(padding=(0, 1))
        body.add_row(avatar)
        body.add_row("")
        body.add_row(title)
        body.add_row(tagline)
        body.add_row("")
        body.add_row(description)
        body.add_row("")
        body.add_row(Text("1 Kontext · 2 Interview · 3 Profil · 4 Korrektur", style="muted"))
        body.add_row(Text("5 Unterlagenabgleich · 6 Finale Antworten", style="muted"))
        body.add_row("")
        body.add_row(Text(f"Modell: {settings.model}", style="muted"))
        body.add_row(Text(f"Ausgabe: {settings.output_file}", style="muted"))
        self.console.print(Panel(body, border_style=BRAND_BLUE, padding=(1, 2)))

    def phase_header(self, number: int) -> None:
        """Sichtbarer Fortschritt verhindert, dass ein längeres Interview wie ein offener Chat wirkt."""
        title = PHASES[number - 1]
        self.console.print()
        self.console.print(
            Rule(
                f"[brand.blue]{number}/{len(PHASES)} · {title}[/brand.blue]",
                style=ACCENT_GOLD,
            )
        )

    def coach_say(
        self,
        message: str,
        *,
        face: str = "friendly",
        subtitle: str = "KI Bewerbungs Coach",
    ) -> None:
        """Alle dialogischen Inhalte bleiben beim Coach, damit Artefakte nicht wie spontane Aussagen wirken."""
        avatar = self._avatar(face)
        body = Panel(
            Markdown(message),
            title=f"[brand.gold]{subtitle}[/brand.gold]",
            border_style=BRAND_BLUE,
            padding=(0, 1),
            expand=True,
        )
        layout = Table.grid(padding=(0, 1))
        layout.add_column(width=7, vertical="top")
        layout.add_column(ratio=1)
        layout.add_row(avatar, body)
        self.console.print(layout)

    def show_document(self, title: str, content: str) -> None:
        """Generierte Ergebnisse erhalten eine eigene visuelle Rolle und sind leichter prüfbar."""
        self.console.print(
            Panel(
                Markdown(content),
                title=f"[brand.blue]{title}[/brand.blue]",
                border_style=ACCENT_GOLD,
                padding=(1, 2),
            )
        )

    def show_notice(self, message: str, *, error: bool = False) -> None:
        """Betriebshinweise stehen außerhalb des Dialogs, damit der Coach keine Systemfehler 'sagt'."""
        style = ALERT_RED if error else BRAND_BLUE
        label = "Fehler" if error else "Hinweis"
        self.console.print(Panel(message, title=label, border_style=style, padding=(0, 1)))

    def ask(self, label: str) -> str:
        return Prompt.ask(f"[question]{label}[/question]")

    def ask_answer(self) -> str:
        return Prompt.ask("[answer]Du[/answer]")

    def multiline_prompt(self, label: str, *, optional: bool = True) -> str:
        """Mehrzeilige Eingabe erleichtert Copy-and-paste, ohne eine Dateiupload-Infrastruktur vorzutäuschen."""
        suffix = " oder **SKIP** zum Überspringen" if optional else ""
        self.coach_say(
            f"**{label}**\n\n"
            f"Füge den Text ein und schreibe anschließend **DONE** "
            f"in eine eigene Zeile{suffix}.",
            face="curious",
        )

        lines: list[str] = []
        while True:
            line = sys.stdin.readline()
            if line == "":
                break
            clean = line.rstrip("\n")
            marker = clean.strip().lower()
            if marker in {"done", "fertig"}:
                break
            if marker in {"skip", "überspringen"} and not lines:
                return ""
            lines.append(clean)
        return "\n".join(lines).strip()

    def status(self, message: str) -> AbstractContextManager[object]:
        """Der Spinner bleibt UI-Verantwortung und koppelt den Provider nicht an Rich."""
        return self.console.status(f"[brand.blue]{message}[/brand.blue]", spinner="dots")
