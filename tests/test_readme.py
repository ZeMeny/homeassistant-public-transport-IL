"""README covers install, the two example stops, and the curlbus caveat."""

from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_documents_install_examples_and_caveat() -> None:
    """The README names HACS, curlbus, line 249, and stops 25629 and 20112."""
    text = README.read_text(encoding="utf-8")
    for token in ("25629", "20112", "249", "HACS", "curlbus"):
        assert token in text
    assert "10120" in text
    assert "10119" in text
    assert "60" in text
    lowered = text.lower()
    assert "no api key" in lowered
    assert "ministry of transport" in lowered
    assert "metropoline" in lowered
    assert "agency 15" in lowered or "agency `15`" in lowered
