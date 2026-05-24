import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402


def test_format_size_kb():
    assert cv._format_size(47_300) == "47.3 KB"


def test_format_size_mb():
    assert cv._format_size(12_500_000) == "12.5 MB"


def test_marker_line_contains_version_and_mtime(tmp_path):
    src = tmp_path / "Договор.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    line = cv.marker_line(src, backend="pdfplumber")
    assert line.startswith(f"<!-- mark-all-the-stuff-down v{cv.__version__} |")
    assert "source: Договор.pdf" in line
    assert f"source_id: {cv._source_id(src)}" in line
    assert "backend: pdfplumber" in line
    assert "mtime:" in line
    assert line.endswith("-->")


def test_compute_output_path_sibling(tmp_path):
    src = tmp_path / "Договор.pdf"
    src.write_bytes(b"x")
    out = cv.compute_output_path(src)
    assert out == tmp_path / "Договор.md"


def test_compute_output_path_collision_uses_mtsd_suffix(tmp_path):
    src = tmp_path / "Договор.pdf"
    src.write_bytes(b"x")
    foreign = tmp_path / "Договор.md"
    foreign.write_text("# someone else's markdown\n", encoding="utf-8")
    out = cv.compute_output_path(src)
    assert out == tmp_path / "Договор.mtsd.md"


def test_compute_output_path_overwrites_own_marker(tmp_path):
    src = tmp_path / "Договор.pdf"
    src.write_bytes(b"x")
    own = tmp_path / "Договор.md"
    own.write_text(cv.marker_line(src, "z") + "\nold\n", encoding="utf-8")
    out = cv.compute_output_path(src)
    assert out == tmp_path / "Договор.md"


def test_compute_output_path_source_mismatch_uses_safe_alternative(tmp_path):
    pdf = tmp_path / "contract.pdf"
    docx = tmp_path / "contract.docx"
    pdf.write_bytes(b"%PDF-1.4 test")
    docx.write_bytes(b"x")
    shared = tmp_path / "contract.md"
    shared.write_text(cv.marker_line(pdf, "pdfplumber") + "\nold\n", encoding="utf-8")
    out = cv.compute_output_path(docx)
    assert out == tmp_path / "contract.mtsd.md"


def test_compute_output_path_avoids_second_source_mismatch(tmp_path):
    pdf = tmp_path / "contract.pdf"
    docx = tmp_path / "contract.docx"
    html = tmp_path / "contract.html"
    for src in (pdf, docx, html):
        src.write_bytes(b"x")
    (tmp_path / "contract.md").write_text(
        cv.marker_line(pdf, "pdfplumber") + "\nold\n", encoding="utf-8"
    )
    (tmp_path / "contract.mtsd.md").write_text(
        cv.marker_line(docx, "docx") + "\nold\n", encoding="utf-8"
    )
    out = cv.compute_output_path(html)
    assert out == tmp_path / "contract.html.mtsd.md"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX perms")
def test_compute_output_path_falls_back_to_cache_when_unwritable(tmp_path, monkeypatch):
    src = tmp_path / "ro" / "Договор.pdf"
    src.parent.mkdir()
    src.write_bytes(b"x")
    monkeypatch.setenv("HOME", str(tmp_path))
    # make parent read-only
    os.chmod(src.parent, 0o500)
    try:
        out = cv.compute_output_path(src)
        assert "mtsd" in str(out)
        assert out.suffix == ".md"
        assert len(out.stem) == 16  # sha256 hex truncated
    finally:
        os.chmod(src.parent, 0o700)


def test_is_up_to_date_returns_true_when_md_newer(tmp_path):
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    md = tmp_path / "doc.md"
    md.write_text(cv.marker_line(src, "x") + "\nbody\n", encoding="utf-8")
    os.utime(md, (time.time() + 10, time.time() + 10))
    assert cv.is_up_to_date(src, md) is True


def test_is_up_to_date_returns_false_when_md_older(tmp_path):
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    md = tmp_path / "doc.md"
    md.write_text(cv.marker_line(src, "x") + "\nbody\n", encoding="utf-8")
    os.utime(md, (1, 1))
    assert cv.is_up_to_date(src, md) is False


def test_is_up_to_date_false_when_no_marker(tmp_path):
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    md = tmp_path / "doc.md"
    md.write_text("no marker here\n", encoding="utf-8")
    assert cv.is_up_to_date(src, md) is False


def test_is_up_to_date_false_when_marker_source_mismatch(tmp_path):
    pdf = tmp_path / "doc.pdf"
    docx = tmp_path / "doc.docx"
    pdf.write_bytes(b"x")
    docx.write_bytes(b"x")
    md = tmp_path / "doc.md"
    md.write_text(cv.marker_line(pdf, "pdfplumber") + "\nbody\n", encoding="utf-8")
    os.utime(md, (time.time() + 10, time.time() + 10))
    assert cv.is_up_to_date(docx, md) is False
