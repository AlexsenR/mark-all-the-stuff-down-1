import sys
import shutil
from pathlib import Path

import pypdf
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402

CORPUS = REPO / "tests" / "corpus"


def test_pdf_probe_detects_simple():
    info = cv._pdf_probe(CORPUS / "Меморандум.pdf")
    assert info.is_scanned is False
    assert info.complexity == "simple"


def test_pdf_probe_detects_table_heavy():
    info = cv._pdf_probe(CORPUS / "Бюджет проекта 2026.pdf")
    assert info.complexity == "complex"
    assert info.table_count >= 2


def test_pdf_probe_detects_multicolumn():
    info = cv._pdf_probe(CORPUS / "статья_журнал.pdf")
    assert info.complexity == "complex"


def test_pdf_probe_detects_scanned():
    info = cv._pdf_probe(CORPUS / "Контракт от 25.05 — окончательная редакция.pdf")
    assert info.is_scanned is True


def test_pdf_probe_accepts_short_text_layer(tmp_path):
    from reportlab.pdfgen import canvas

    src = tmp_path / "short.pdf"
    c = canvas.Canvas(str(src))
    c.drawString(72, 720, "OK")
    c.save()

    info = cv._pdf_probe(src)

    assert info.is_scanned is False


def test_dispatch_pdf_simple(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "Меморандум.pdf")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 0, r.stderr
    md = src.with_suffix(".md")
    assert "Меморандум" in md.read_text(encoding="utf-8")


@pytest.mark.ocr
def test_dispatch_pdf_scanned_converts_via_ocr(run_convert, tmp_copy):
    """Scanned PDFs are no longer a hard error; they OCR successfully."""
    if not shutil.which("tesseract"):
        pytest.skip("tesseract not on PATH")
    if not shutil.which("pdftoppm"):
        pytest.skip("pdftoppm not on PATH")
    src = tmp_copy(CORPUS / "Контракт от 25.05 — окончательная редакция.pdf")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 0, r.stderr
    md = src.with_suffix(".md")
    body = md.read_text(encoding="utf-8")
    first = body.splitlines()[0]
    assert first.startswith("<!-- mark-all-the-stuff-down v0.1.0 ")
    assert "backend: tesseract-ocr" in first
    assert "## Page 1" in body


def test_dispatch_pdf_scanned_without_tesseract_is_ocr_failed(
    run_convert, tmp_copy, tmp_path
):
    """When tesseract is unavailable, surface ocr-failed, not scanned-pdf."""
    src = tmp_copy(CORPUS / "Контракт от 25.05 — окончательная редакция.pdf")
    r = run_convert(
        src,
        env={"MTSD_FORCE_PREINSTALLED": "1", "PATH": str(tmp_path)},
    )
    assert r.returncode == 1
    assert "ERROR ocr-failed" in r.stderr
    assert "scanned-pdf" not in r.stderr


def test_dispatch_pdf_corrupt_errors_as_corrupted(run_convert, tmp_path):
    src = tmp_path / "corrupt.pdf"
    src.write_bytes(b"%PDF-1.4\nnot a real pdf")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR corrupted" in r.stderr


def test_dispatch_pdf_password_protected_errors_as_protected(run_convert, tmp_path):
    src = tmp_path / "password.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    with src.open("wb") as fh:
        writer.write(fh)

    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR protected" in r.stderr
