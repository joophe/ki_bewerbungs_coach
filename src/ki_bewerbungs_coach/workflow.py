"""Linearer Interview- und Schreibworkflow."""

from __future__ import annotations

from .config import Settings
from .llm import EmptyModelResponse, LLMService
from .output import CoachResult
from .prompts import (
    CRITICAL_REVIEWER_FALLBACK_PROMPT,
    CRITICAL_REVIEWER_PROMPT,
    REFINEMENT_PROMPT,
    SHARPENING_PROMPT,
    SYNTHESIS_PROMPT,
    WRITER_PROMPT,
    build_interviewer_prompt,
)
from .ui import TerminalUI

FINISH_TOKEN = "##FERTIG##"
STOP_COMMANDS = {"fertig", "stop", "ende", "exit", "quit"}


class CoachWorkflow:
    """Die Phasen bleiben explizit, weil Nachvollziehbarkeit wichtiger ist als ein generischer Agentengraph."""

    def __init__(self, settings: Settings, llm: LLMService, ui: TerminalUI) -> None:
        self.settings = settings
        self.llm = llm
        self.ui = ui

    def run(self) -> CoachResult:
        context, job_text = self.phase_context()
        interview = self.phase_interview(context, job_text)
        profile = self.phase_synthesis(interview)
        profile = self.phase_reflection(profile)
        gap_analysis, job_text = self.phase_sharpening(profile, job_text)
        draft, final_review = self.phase_write(profile, gap_analysis, job_text)
        return CoachResult(profile, gap_analysis, draft, final_review)

    def phase_context(self) -> tuple[str, str]:
        """Nur der notwendige Rahmen wird erfasst, um das Interview nicht vorzeitig zu verengen."""
        self.ui.phase_header(1)
        self.ui.coach_say(
            "Zuerst brauche ich nur den Rahmen. Die Angaben helfen mir, relevante "
            "Erfahrungen zu vertiefen; sie bestimmen aber nicht vorab, wie dein Profil aussehen soll."
        )
        current = self.ui.ask("Deine aktuelle Rolle oder Position")
        target = self.ui.ask("Zielrolle in wenigen Worten")
        job_text = self.ui.multiline_prompt(
            "Optional: vollständige Stellenausschreibung",
            optional=True,
        )
        if not job_text:
            self.ui.show_notice(
                "Die Stellenausschreibung wurde übersprungen. Das Interview funktioniert trotzdem."
            )

        context = f"Aktuelle Rolle: {current}\nAngestrebte Stelle: {target}"
        if job_text:
            context += f"\n\nStellenbeschreibung:\n{job_text}"
        return context, job_text

    def phase_interview(
        self,
        context: str,
        job_text: str = "",
    ) -> list[dict[str, str]]:
        """Konkrete Situationen liefern belastbarere Hinweise als direkt abgefragte Eigenschaftslisten."""
        self.ui.phase_header(2)
        self.ui.coach_say(
            "Ich stelle dir nacheinander höchstens "
            f"**{self.settings.max_questions} Fragen**. Konkrete Situationen sind hilfreicher "
            "als perfekte Antworten. Mit **STOP** kannst du das Interview jederzeit beenden.",
            face="curious",
        )

        messages: list[dict[str, str]] = []
        prompt = build_interviewer_prompt(job_text, self.settings.max_questions)
        response = self.llm.complete(prompt, messages, context)
        answered = 0

        while answered < self.settings.max_questions:
            question, finished = strip_finish_token(response)
            if finished or not question:
                break

            self.ui.coach_say(
                question,
                face="curious",
                subtitle=f"KI Bewerbungs Coach · Frage {answered + 1}",
            )
            user_input = self.ui.ask_answer()
            if is_stop_command(user_input):
                break

            answered += 1
            response = self.llm.complete(prompt, messages, user_input)

        self.ui.show_notice(f"Interview abgeschlossen: {answered} Antwort(en) erfasst.")
        return messages

    def phase_synthesis(self, interview: list[dict[str, str]]) -> str:
        """Das erste Profil bleibt eine überprüfbare Hypothese und wird nicht als Diagnose präsentiert."""
        self.ui.phase_header(3)
        self.ui.coach_say(
            "Ich verdichte jetzt deine Beispiele zu einem ersten Profil. Der Entwurf ist eine "
            "Arbeitshypothese – du korrigierst ihn im nächsten Schritt.",
            face="thinking",
        )
        transcript = build_transcript(interview)
        profile = self.llm.complete(
            SYNTHESIS_PROMPT,
            [],
            f"Interview-Transkript:\n\n{transcript}",
        )
        self.ui.show_document("Arbeitsstil-Profil · Entwurf", profile)
        return profile

    def phase_reflection(self, profile: str) -> str:
        """Die Person korrigiert die Interpretation, bevor sie als Grundlage für Bewerbungsinhalte dient."""
        self.ui.phase_header(4)
        self.ui.coach_say(
            "Jetzt hast du die Deutungshoheit: Was trifft zu, was ist falsch, was fehlt oder ist "
            "zu stark formuliert? Mit **SKIP** übernimmst du den Entwurf unverändert.",
            face="curious",
        )
        feedback = self.ui.multiline_prompt("Dein Feedback zum Profil", optional=True)
        if not feedback:
            self.ui.show_notice("Profil unverändert übernommen.")
            return profile

        refined = self.llm.complete(
            REFINEMENT_PROMPT,
            [],
            f"Ursprüngliches Profil:\n\n{profile}\n\nFeedback der Person:\n\n{feedback}",
        )
        self.ui.show_document("Arbeitsstil-Profil · validierte Fassung", refined)
        return refined

    def phase_sharpening(self, profile: str, job_text: str = "") -> tuple[str, str]:
        """Der optionale Abgleich sucht Lücken und Widersprüche statt künstlicher Stellenpassung."""
        self.ui.phase_header(5)
        self.ui.coach_say(
            "Optional kann ich dein Profil mit Lebenslauf oder Anschreiben abgleichen. "
            "Dabei suche ich nicht nach einer künstlich perfekten Passung, sondern nach Lücken, "
            "Übertreibungen und bisher unsichtbaren Stärken.",
            face="curious",
        )
        documents = self.ui.multiline_prompt("CV oder Anschreiben", optional=True)
        if not documents:
            self.ui.show_notice("Abgleich mit Unterlagen übersprungen.")
            return "", job_text

        if not job_text:
            job_text = self.ui.multiline_prompt("Optional: Stellenausschreibung", optional=True)

        context = f"Validiertes Arbeitsstil-Profil:\n\n{profile}\n\nUnterlagen:\n\n{documents}"
        if job_text:
            context += f"\n\nStellenbeschreibung:\n\n{job_text}"

        analysis = self.llm.complete(SHARPENING_PROMPT, [], context)
        self.ui.show_document("Abgleich · Profil, Unterlagen und Zielrolle", analysis)
        return analysis, job_text

    def phase_write(
        self,
        profile: str,
        gap_analysis: str,
        job_text: str,
    ) -> tuple[str, str]:
        """Ein getrennter Review verhindert, dass sprachliche Glätte als Faktentreue missverstanden wird."""
        self.ui.phase_header(6)
        self.ui.coach_say(
            "Aus deinem validierten Profil entstehen jetzt die fünf Antworten. Anschließend prüfe "
            "ich sie noch einmal auf Übertreibungen, unbelegte Aussagen und unnötige Floskeln.",
            face="thinking",
        )

        context = f"Validiertes Arbeitsstil-Profil:\n\n{profile}"
        if gap_analysis:
            context += f"\n\nGap-Analyse:\n\n{gap_analysis}"
        if job_text:
            context += f"\n\nStellenbeschreibung:\n\n{job_text}"

        draft = self.llm.complete(WRITER_PROMPT, [], context)
        self.ui.show_document("Antworten · erster Entwurf", draft)

        review_context = f"Bewerbungstext:\n\n{draft}\n\nValidiertes Profil:\n\n{profile}"
        if job_text:
            review_context += f"\n\nStellenbeschreibung:\n\n{job_text}"

        try:
            final = self.llm.complete(CRITICAL_REVIEWER_PROMPT, [], review_context)
            self.ui.show_document("Kritisches Review und finale Fassung", final)
            return draft, final
        except EmptyModelResponse as exc:
            self.ui.show_notice(
                "Das ausführliche Review konnte nicht erzeugt werden. "
                "Ich versuche eine kompakte Überarbeitung nur auf Basis des Entwurfs.\n"
                f"Details: {exc}"
            )

        try:
            final = self.llm.complete(
                CRITICAL_REVIEWER_FALLBACK_PROMPT,
                [],
                f"Erster Entwurf:\n\n{draft}",
            )
            self.ui.show_document("Finale Fassung · kompakter Fallback", final)
            return draft, final
        except EmptyModelResponse as exc:
            self.ui.show_notice(
                "Auch der kompakte Wiederholungsversuch blieb ohne Textantwort. "
                "Der erste Entwurf wird trotzdem gespeichert; der Review-Schritt kann später "
                f"erneut ausgeführt werden.\nDetails: {exc}",
                error=True,
            )
            return draft, ""


def is_stop_command(value: str) -> bool:
    return value.strip().lower() in STOP_COMMANDS


def strip_finish_token(response: str) -> tuple[str, bool]:
    finished = FINISH_TOKEN in response
    return response.replace(FINISH_TOKEN, "").strip(), finished


def build_transcript(messages: list[dict[str, str]]) -> str:
    labels = {"assistant": "Coach", "user": "Person"}
    return "\n".join(
        f"{labels.get(item['role'], item['role'])}: {item['content']}"
        for item in messages
    )
