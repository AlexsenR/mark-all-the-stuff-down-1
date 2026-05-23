from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "tests" / "corpus"


def test_doc_unsupported(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "report_1998.doc")
    r = run_convert(src)
    assert r.returncode == 1
    assert "ERROR unsupported" in r.stderr
    assert ".doc" in r.stderr


def test_xls_install_failed_in_preinstalled_mode(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "legacy_export.xls")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR install-failed" in r.stderr


def test_rtf_install_failed_in_preinstalled_mode(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "Постановление № 1234-р.rtf")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR install-failed" in r.stderr


def test_epub_install_failed_in_preinstalled_mode(run_convert, tmp_copy):
    src = tmp_copy(CORPUS / "Гражданский_кодекс_РФ_часть_первая.epub")
    r = run_convert(src, env={"MTSD_FORCE_PREINSTALLED": "1"})
    assert r.returncode == 1
    assert "ERROR install-failed" in r.stderr
