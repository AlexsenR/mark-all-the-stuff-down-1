import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402

CORPUS = REPO / "tests" / "corpus"


def test_xlsx_direct_renders_multisheet():
    body = cv._convert_xlsx_direct(CORPUS / "Расчёт неустойки.xlsx")
    assert "## Расчёт" in body
    assert "## Неустойка" in body


def test_xlsx_direct_renders_raw_formula_when_no_cache():
    body = cv._convert_xlsx_direct(CORPUS / "Расчёт неустойки.xlsx")
    # openpyxl can't evaluate, so cached_value is None -> raw "=A2+B2"
    assert "=A2+B2" in body


def test_xlsx_direct_renders_merged_cells():
    body = cv._convert_xlsx_direct(CORPUS / "Финмодель v3.xlsx")
    assert "Заголовок таблицы" in body
    # merged: value once, then empty cells
    lines = body.splitlines()
    header_line = next(l for l in lines if "Заголовок таблицы" in l)
    # the merged row should be a single value followed by empty pipe cells
    assert header_line.count("Заголовок таблицы") == 1


def test_dispatch_xlsx_clients(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "Реестр клиентов 2026.xlsx")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 0, r.stderr
    text = src.with_suffix(".md").read_text(encoding="utf-8")
    assert "Иванов И.И." in text
    assert "## Клиенты" in text


def test_dispatch_xlsx_corrupt_errors_as_corrupted(run_convert, tmp_path):
    src = tmp_path / "corrupt.xlsx"
    src.write_bytes(b"not an xlsx")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR corrupted" in r.stderr
