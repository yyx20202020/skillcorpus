from pathlib import Path

from skillcorpus.extractors.html import extract, html_to_text
from skillcorpus.segment import segment_document

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "html_inline" / "chapters.html"


def test_inline_spans_do_not_break_chapter_words():
    text = html_to_text(FIXTURE.read_text(encoding="utf-8"))
    assert "Chapter 1" in text.replace("\n", " ") or "Chapter 1:" in text
    assert "Chapter\n1" not in text
    assert "hypertext" in text
    assert 'print("ok")' in text or "print(\"ok\")" in text


def test_code_block_compiles_after_extraction():
    text = html_to_text(FIXTURE.read_text(encoding="utf-8"))
    # Pull the indented code region.
    start = text.index("if enabled:")
    snippet = text[start : text.index("Chapter 2")].strip()
    # Normalize possible trailing prose.
    lines = []
    for line in snippet.splitlines():
        if line.strip().startswith("Chapter"):
            break
        lines.append(line)
    code = "\n".join(lines)
    compile(code, "<fixture>", "exec")


def test_html_extract_segments_two_chapters():
    doc = extract(FIXTURE)
    chunks = segment_document(doc)
    titles = " ".join(c.title for c in chunks)
    assert "1" in titles and "2" in titles
