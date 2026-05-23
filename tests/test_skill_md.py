from pathlib import Path
import re

SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"


def test_skill_md_exists():
    assert SKILL.is_file()


def test_skill_md_frontmatter_has_name_and_paths():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "must start with YAML frontmatter"
    end = text.index("\n---\n", 4)
    fm = text[4:end]
    assert "name: mark-all-the-shit-down" in fm
    for ext in (
        ".docx",
        ".pdf",
        ".xlsx",
        ".xls",
        ".pptx",
        ".rtf",
        ".html",
        ".epub",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".tif",
        ".bmp",
        ".webp",
    ):
        assert f'"*{ext}"' in fm, f"missing path pattern for {ext}"


def test_skill_md_instructs_offset_limit():
    text = SKILL.read_text(encoding="utf-8")
    assert re.search(r"offset.*limit|limit.*offset", text, re.IGNORECASE)


def test_skill_md_instructs_batch_jobs():
    text = SKILL.read_text(encoding="utf-8")
    assert "--jobs" in text
    assert re.search(r"multiple|parallel|нескольк|параллел", text, re.IGNORECASE)


def test_skill_md_warns_about_doc():
    text = SKILL.read_text(encoding="utf-8")
    assert ".doc" in text and "не поддерж" in text.lower() or "not supported" in text.lower()
