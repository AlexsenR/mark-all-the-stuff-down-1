import builtins
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402

CORPUS = REPO / "tests" / "corpus"


def test_html_direct_basic_headings_and_links():
    body = cv._convert_html_direct(CORPUS / "report.html")
    assert "# Report" in body
    assert "[link](https://example.com)" in body


def test_html_direct_table_rendered_as_pipes():
    body = cv._convert_html_direct(CORPUS / "судебная_практика.html")
    assert "ООО Альфа" in body
    assert "| Дело |" in body or "| А40-1 |" in body


def test_dispatch_html_writes_md(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "судебная_практика.html")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 0, r.stderr
    text = src.with_suffix(".md").read_text(encoding="utf-8")
    assert "Судебная практика" in text


def test_html_direct_raises_backend_unavailable_without_bs4(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "bs4":
            raise ImportError("blocked bs4")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(cv.BackendUnavailable, match="beautifulsoup4 not installed"):
        cv._convert_html_direct(CORPUS / "report.html")
