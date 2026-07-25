from types import SimpleNamespace

from ki_bewerbungs_coach.llm import extract_anthropic_text, extract_openai_text


def test_extract_openai_string_content() -> None:
    message = SimpleNamespace(content="  Antwort  ")
    assert extract_openai_text(message) == "Antwort"


def test_extract_openai_structured_content() -> None:
    message = SimpleNamespace(
        content=[
            {"type": "text", "text": "Teil eins"},
            SimpleNamespace(text="Teil zwei"),
        ]
    )
    assert extract_openai_text(message) == "Teil eins\nTeil zwei"


def test_extract_openai_empty_content() -> None:
    assert extract_openai_text(SimpleNamespace(content=None)) == ""


def test_extract_anthropic_multiple_text_blocks() -> None:
    blocks = [
        SimpleNamespace(type="text", text="Teil eins"),
        SimpleNamespace(type="tool_use", text=None),
        SimpleNamespace(type="text", text="Teil zwei"),
    ]
    assert extract_anthropic_text(blocks) == "Teil einsTeil zwei"
