"""Terminaldarstellung und Nutzereingaben."""

from __future__ import annotations

import os
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

# Zwei Farbpaletten, damit derselbe Code auf dunklen Terminals (CLI) und auf dem
# hellen, freundlichen Hintergrund der Web-Demo lesbar bleibt. Die Web-Version
# setzt COACH_THEME=light; die CLI bleibt standardmäßig dunkel.
_DARK_PALETTE = {
    "brand_blue": "#5B9BFF",
    "accent_gold": "#F4B400",
    "alert_red": "#FF6B6B",
    "ink": "#E5E7EB",
    "muted": "#9CA3AF",
}
_LIGHT_PALETTE = {
    "brand_blue": "#1A56DB",   # kräftiges Blau, gut lesbar auf Hell
    "accent_gold": "#B45309",  # tiefes Amber statt hellem Gold (Kontrast auf Hell)
    "alert_red": "#C5221F",
    "ink": "#1F2937",
    "muted": "#6B7280",
}

_PALETTE = _LIGHT_PALETTE if os.getenv("COACH_THEME", "dark").strip().lower() == "light" else _DARK_PALETTE

BRAND_BLUE = _PALETTE["brand_blue"]
ACCENT_GOLD = _PALETTE["accent_gold"]
ALERT_RED = _PALETTE["alert_red"]
TEXT_INK = _PALETTE["ink"]
TEXT_MUTED = _PALETTE["muted"]

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


# Unterhalb dieser Terminalbreite wird kompakter gerendert (schmale Browser,
# Tablet, Smartphone): weniger Padding, keine Avatar-Seitenspalte. Sonst passen
# Rahmen und Text nicht mehr in die verfügbaren Spalten und verschachteln sich.
NARROW_WIDTH = 64


class TerminalUI:
    """Eine konsistente Oberfläche trennt Coach-Dialog, Dokumente und Systemzustände."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(theme=THEME, highlight=False)

    @property
    def _is_narrow(self) -> bool:
        """Wird pro Ausgabe geprüft, damit sich die Darstellung an die aktuelle Breite anpasst."""
        return self.console.width < NARROW_WIDTH

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
        if settings.write_output_file:
            body.add_row(Text(f"Ausgabe: {settings.output_file}", style="muted"))
        padding = (0, 1) if self._is_narrow else (1, 2)
        self.console.print(Panel(body, border_style=BRAND_BLUE, padding=padding))

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
        body = Panel(
            Markdown(message),
            title=f"[brand.gold]{subtitle}[/brand.gold]",
            border_style=BRAND_BLUE,
            padding=(0, 1),
            expand=True,
        )
        if self._is_narrow:
            # Auf schmalen Terminals keine Avatar-Seitenspalte: das Panel nutzt
            # die volle Breite, statt sich mit dem Avatar zu verschachteln.
            self.console.print(body)
            return
        avatar = self._avatar(face)
        layout = Table.grid(padding=(0, 1))
        layout.add_column(width=7, vertical="top")
        layout.add_column(ratio=1)
        layout.add_row(avatar, body)
        self.console.print(layout)

    def show_document(self, title: str, content: str) -> None:
        """Generierte Ergebnisse erhalten eine eigene visuelle Rolle und sind leichter prüfbar."""
        padding = (0, 1) if self._is_narrow else (1, 2)
        self.console.print(
            Panel(
                Markdown(content),
                title=f"[brand.blue]{title}[/brand.blue]",
                border_style=ACCENT_GOLD,
                padding=padding,
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
