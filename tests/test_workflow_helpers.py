from ki_bewerbungs_coach.workflow import (
    build_transcript,
    is_stop_command,
    strip_finish_token,
)


def test_stop_commands_are_case_and_whitespace_insensitive() -> None:
    assert is_stop_command("  STOP ")
    assert is_stop_command("Fertig")
    assert not is_stop_command("weiter")


def test_strip_finish_token_returns_clean_text_and_flag() -> None:
    text, finished = strip_finish_token("Danke. ##FERTIG##")
    assert text == "Danke."
    assert finished is True


def test_build_transcript_uses_readable_roles() -> None:
    messages = [
        {"role": "assistant", "content": "Frage"},
        {"role": "user", "content": "Antwort"},
    ]
    assert build_transcript(messages) == "Coach: Frage\nPerson: Antwort"
