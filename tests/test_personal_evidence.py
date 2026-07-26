from ki_bewerbungs_coach.workflow import count_anchor_situations


def test_counts_multiple_anchor_situations() -> None:
    profile = (
        "## Belegbank\n"
        "### Situation 1 — MCP-Server\n- **Ausgangslage:** ...\n"
        "### Situation 2 — Paperanalyse\n- **Ausgangslage:** ...\n"
        "### Situation 3 — PATH-Bug\n- **Ausgangslage:** ...\n"
    )
    assert count_anchor_situations(profile) == 3


def test_heading_match_is_case_insensitive() -> None:
    assert count_anchor_situations("### situation 1 — klein geschrieben") == 1


def test_ignores_unrelated_headings() -> None:
    profile = (
        "## Belegte Stärken\n"
        "### Passendes Umfeld\n"
        "### Situationsbeschreibung ohne Nummer\n"
    )
    assert count_anchor_situations(profile) == 0


def test_returns_zero_without_belegbank() -> None:
    assert count_anchor_situations("## Profil in drei Sätzen\nKein Beleg.") == 0
