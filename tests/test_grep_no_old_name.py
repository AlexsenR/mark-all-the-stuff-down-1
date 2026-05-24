import re
from pathlib import Path

CONVERT = Path(__file__).resolve().parents[1] / "convert.py"


def test_no_old_skill_name_in_convert():
    text = CONVERT.read_text(encoding="utf-8")
    assert re.search(r"(?<!-)\bmark-the-stuff-down\b", text) is None
    assert "0.2.0" not in text


def test_no_old_repo_slug_in_convert():
    text = CONVERT.read_text(encoding="utf-8")
    assert re.search(r"(?<!-)\bmark-the-shit-down\b", text) is None


def test_new_marker_prefix_constant():
    text = CONVERT.read_text(encoding="utf-8")
    assert '"<!-- mark-all-the-stuff-down v"' in text or (
        "'<!-- mark-all-the-stuff-down v'" in text
    )
