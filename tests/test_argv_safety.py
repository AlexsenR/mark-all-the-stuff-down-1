import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402


def test_safe_argv_returns_original_when_ascii(tmp_path):
    src = tmp_path / "plain.docx"
    src.write_bytes(b"x")
    with cv._with_safe_argv_path(src) as p:
        assert p == src


def test_safe_argv_copies_when_unicode_unencodable(tmp_path, monkeypatch):
    src = tmp_path / "Договор.docx"
    src.write_bytes(b"data")
    # force fallback by claiming non-utf8 stdin encoding
    monkeypatch.setattr(cv, "_argv_is_safe", lambda _: False)
    with cv._with_safe_argv_path(src) as p:
        assert p != src
        assert p.read_bytes() == b"data"
        assert p.suffix == ".docx"
        assert p.name.isascii()
    assert not p.exists()  # cleaned up
