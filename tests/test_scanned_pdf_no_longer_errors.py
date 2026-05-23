import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _make_scanned_pdf(path: Path) -> None:
    """Build an image-only PDF: rasterized text drawn as an image."""
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    d.text((100, 200), "HELLO OCR", fill="black", font=font)
    img.save(path, "PDF", resolution=150.0)


@pytest.mark.ocr
def test_scanned_pdf_converts(tmp_path):
    if not shutil.which("tesseract"):
        pytest.skip("tesseract not on PATH")
    if not shutil.which("pdftoppm"):
        pytest.skip("pdftoppm not on PATH")
    src = tmp_path / "scan.pdf"
    _make_scanned_pdf(src)

    res = subprocess.run(
        [sys.executable, str(ROOT / "convert.py"), str(src)],
        capture_output=True,
        text=True,
    )

    assert res.returncode == 0, f"stderr={res.stderr}"
    out_md = src.with_suffix(".md")
    assert out_md.exists()
    body = out_md.read_text(encoding="utf-8")
    assert body.startswith("<!-- mark-all-the-shit-down v0.1.0 ")
    assert "## Page 1" in body
    assert "backend: tesseract-ocr" in body.splitlines()[0]


@pytest.mark.ocr
def test_image_converts(tmp_path):
    if not shutil.which("tesseract"):
        pytest.skip("tesseract not on PATH")
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (480, 120), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    d.text((10, 30), "HELLO OCR", fill="black", font=font)
    src = tmp_path / "hello.png"
    img.save(src)

    res = subprocess.run(
        [sys.executable, str(ROOT / "convert.py"), str(src)],
        capture_output=True,
        text=True,
    )

    assert res.returncode == 0, f"stderr={res.stderr}"
    out_md = src.with_suffix(".md")
    assert out_md.exists()
    body = out_md.read_text(encoding="utf-8")
    assert body.startswith("<!-- mark-all-the-shit-down v0.1.0 ")
    assert "<!-- ocr conf=" in body
    assert "## Page" not in body
    assert "backend: tesseract-ocr" in body.splitlines()[0]
