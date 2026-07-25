from pathlib import Path

from ki_bewerbungs_coach.output import CoachResult, render_output, write_output


def test_render_output_includes_optional_sections() -> None:
    result = CoachResult(
        profile="Profil",
        gap_analysis="Analyse",
        draft="Entwurf",
        final_review="Finale Fassung",
    )
    content = render_output(result)

    assert "## Abgleich mit Unterlagen" in content
    assert "## Kritisches Review und finale Fassung" in content
    assert "Finale Fassung" in content


def test_render_output_marks_missing_review() -> None:
    result = CoachResult("Profil", "", "Entwurf", "")
    content = render_output(result)

    assert "## Abgleich mit Unterlagen" not in content
    assert "keine Textantwort" in content


def test_write_output_replaces_file_atomically(tmp_path: Path) -> None:
    target = tmp_path / "result.md"
    write_output(target, "vollständig")

    assert target.read_text(encoding="utf-8") == "vollständig"
    assert not target.with_suffix(".md.tmp").exists()
