# Konzept: KI Bewerbungs Coach

Diese Notiz beschreibt die tragenden Entwurfsentscheidungen hinter dem Coach. Sie ergänzt
das [README](../README.md) um das *Warum* und bleibt bewusst nah am tatsächlichen Code.

## Problem

Ein Sprachmodell schreibt auf Zuruf schnell einen flüssigen Bewerbungstext. Das eigentliche
Risiko ist nicht die Sprache, sondern die **Austauschbarkeit**: Antworten klingen
professionell, könnten aber nahezu unverändert von einer anderen Person stammen. Ein erster
Prototyp bestätigte genau das – konkrete Interviewinhalte wurden bei der Verdichtung wieder
zu allgemeinen Aussagen.

## Leitidee

Persönliche Kontur entsteht nicht aus besseren Formulierungen, sondern aus **belegten
Situationen**. Der Coach trennt deshalb drei Ebenen:

1. **Evidenz sammeln** – konkrete Ankersituationen statt Selbsteinschätzungen.
2. **Evidenz sichern** – in einer strukturierten Belegbank, die die Person prüft und freigibt.
3. **Formulieren** – erst am Ende, gebunden an die Belegbank, mit anschließendem Review.

## Ankersituationen und Belegbank

Eine Ankersituation gilt erst als vollständig, wenn Ausgangslage, eigener Beitrag,
Schwierigkeit und Ergebnis erkennbar sind (`build_interviewer_prompt`). Die Synthese hält
sie in einer festen Markdown-Struktur fest (`SYNTHESIS_PROMPT`, Abschnitt *Belegbank*).
Fehlende Bestandteile werden mit `Offen:` markiert statt erfunden.

Damit ein glattes Profil nicht unbemerkt ohne Beispiele bleibt, prüft ein **deterministischer
Check** die Anzahl der Ankersituationen (`count_anchor_situations`) und warnt sichtbar, wenn
weniger als drei vorliegen (`_show_anchor_notice`). Die Regel wird bewusst außerhalb des
Modells geprüft – nicht der Text soll sich selbst zufrieden bewerten.

## Sprachliche Anker

Charakteristische Formulierungen der Person werden erfasst und beim Schreiben bewahrt.
Ebenso werden Aussagen markiert, die zwar professionell klingen, aber *nicht nach der
Person*. So bleibt der Ton erkennbar, ohne dass eine künstliche Persona entsteht.

## Austauschbarkeitstest

Das abschließende Review (`CRITICAL_REVIEWER_PROMPT`) prüft ausdrücklich, ob eine Antwort
auch von einer anderen Person mit ähnlicher Zielrolle stammen könnte. Austauschbare Passagen
werden mit einer passenden Ankersituation verbunden – oder, falls kein Beleg existiert,
vorsichtiger formuliert statt ausgeschmückt.

## Warum die Person die Deutungshoheit behält

Profil und Belegbank sind ein Entwurf, keine Diagnose. Vor der Nutzung korrigiert, ergänzt
oder anonymisiert die Person die Situationen (`phase_reflection`). Das Transkript wird als
zusätzliche Evidenz durchgereicht, damit Synthese, Review und Schreibschritt auf denselben
belegten Aussagen arbeiten.

## Bewusste Grenzen

- Der Coach ist ein CLI-MVP, kein psychologisches Instrument.
- Er prüft Aussagen nicht gegen externe Nachweise.
- Die Qualität hängt von Modell, Gesprächslänge und Eingabequalität ab.
- Die finale inhaltliche Verantwortung und Freigabe liegen immer bei der Person.
