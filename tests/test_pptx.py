import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import convert as cv  # noqa: E402

CORPUS = REPO / "tests" / "corpus"


def test_pptx_direct_renders_title_and_body():
    body = cv._convert_pptx_direct(CORPUS / "Кейс для клиента — заметки.pptx")
    assert "Кейс для клиента" in body
    assert "позиции" in body


def test_pptx_direct_renders_notes():
    body = cv._convert_pptx_direct(CORPUS / "Кейс для клиента — заметки.pptx")
    assert "confidential" in body.lower() or "Note" in body


def test_dispatch_pptx_with_images_no_llm(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "Презентация с картинками.pptx")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 0, r.stderr
    md = src.with_suffix(".md").read_text(encoding="utf-8")
    for forbidden in (
        "This image shows",
        "The image depicts",
        "A photo of",
        "На изображении",
    ):
        assert forbidden not in md


def test_dispatch_pptx_corrupt_errors_as_corrupted(run_convert, tmp_path):
    src = tmp_path / "corrupt.pptx"
    src.write_bytes(b"not a pptx")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR corrupted" in r.stderr


def test_dispatch_pptx_malformed_xml_errors_as_corrupted(run_convert, tmp_path):
    src = tmp_path / "malformed-xml.pptx"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("[Content_Types].xml", b"<Types><Override")

    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR corrupted" in r.stderr
