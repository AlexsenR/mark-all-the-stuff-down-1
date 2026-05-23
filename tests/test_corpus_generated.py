from pathlib import Path
import os
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "tests" / "corpus"


def test_corpus_generation_creates_all_files(tmp_path):
    corpus = tmp_path / "corpus"
    subprocess.run(
        [sys.executable, str(REPO / "tests" / "generate_corpus.py")],
        check=True,
        cwd=REPO,
        env={**os.environ, "MTSD_CORPUS_ROOT": str(corpus)},
    )
    expected = [
        "simple_letter.docx",
        "Договор поставки № 47.docx",
        "Соглашение (с правками).docx",
        "Договор №1 от 25.05.2026.docx",
        "report_1998.doc",
        "Меморандум.pdf",
        "статья_журнал.pdf",
        "Бюджет проекта 2026.pdf",
        "Контракт от 25.05 — окончательная редакция.pdf",
        "protected.pdf",
        "Реестр клиентов 2026.xlsx",
        "Финмодель v3.xlsx",
        "Расчёт неустойки.xlsx",
        "legacy_export.xls",
        "Презентация (исправлено).pptx",
        "Кейс для клиента — заметки.pptx",
        "Презентация с картинками.pptx",
        "Постановление № 1234-р.rtf",
        "судебная_практика.html",
        "report.html",
        "Гражданский_кодекс_РФ_часть_первая.epub",
    ]
    for name in expected:
        p = corpus / name
        assert p.is_file(), f"missing {name}"
        assert p.stat().st_size > 0


def test_corpus_expected_jsons_exist():
    exp = CORPUS / "expected"
    assert exp.is_dir()
    assert len(list(exp.glob("*.json"))) >= 20
